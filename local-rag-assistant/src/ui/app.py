"""
src/ui/app.py
Streamlit UI with two tabs:
  1. Chat — ask questions about your Notion notes
  2. Timeline — monthly activity charts and AI summaries
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as: streamlit run src/ui/app.py from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import altair as alt
import streamlit as st

from src.config import get_config
from src.ingest.embedder import embed_query
from src.query.analytics import summarize_period
from src.query.generator import generate_answer_stream
from src.query.retriever import HybridRetriever
from src.store.event_store import Analytics, EventStore
from src.store.vector_store import VectorStore


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Notion Assistant",
    page_icon="🧠",
    layout="wide",
)

# ── Load config + stores (cached) ─────────────────────────────────────────────

@st.cache_resource
def load_resources():
    cfg = get_config()
    vector_store = VectorStore(cfg.paths.chroma_db)
    event_store = EventStore(cfg.paths.sqlite_db)
    analytics = Analytics(cfg.paths.sqlite_db)
    retriever = HybridRetriever(
        vector_store=vector_store,
        embedding_model=cfg.models.embeddings,
        bm25_weight=cfg.retrieval.bm25_weight,
        vector_weight=cfg.retrieval.vector_weight,
    )
    return cfg, vector_store, event_store, analytics, retriever


cfg, vector_store, event_store, analytics, retriever = load_resources()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🧠 Notion Assistant")
    st.markdown("---")
    chunk_count = vector_store.count()
    event_count = event_store.count()
    st.metric("Chunks indexed", f"{chunk_count:,}")
    st.metric("Events extracted", f"{event_count:,}")
    st.markdown("---")
    st.caption(f"LLM: `{cfg.models.llm}`")
    st.caption(f"Embeddings: `{cfg.models.embeddings}`")

    if chunk_count == 0:
        st.warning("No data indexed yet.\nRun: `python scripts/run_ingest.py`")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_chat, tab_timeline = st.tabs(["💬 Chat", "📅 Timeline"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ═══════════════════════════════════════════════════════════════════════════════

with tab_chat:
    st.header("Ask your notes")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_citations" not in st.session_state:
        st.session_state.last_citations = []

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("What did I work on in Q3? What did I learn about X?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if chunk_count == 0:
            st.error("No data indexed. Run `python scripts/run_ingest.py` first.")
        else:
            with st.chat_message("assistant"):
                with st.spinner("Searching your notes..."):
                    hits = retriever.retrieve(prompt, top_k=cfg.retrieval.top_k)

                # Stream the answer
                answer_placeholder = st.empty()
                full_answer = ""
                for token in generate_answer_stream(prompt, hits, model=cfg.models.llm):
                    full_answer += token
                    answer_placeholder.markdown(full_answer + "▌")
                answer_placeholder.markdown(full_answer)

                # Citations
                if hits:
                    with st.expander(f"📎 Sources ({len(set(h['source_path'] for h in hits))} pages)"):
                        seen = set()
                        for hit in hits:
                            if hit["source_path"] not in seen:
                                seen.add(hit["source_path"])
                                score = hit.get("combined_score", hit.get("score", 0))
                                st.markdown(
                                    f"- **{hit['title']}** — `{hit['source_path']}` "
                                    f"_(relevance: {score:.2f})_"
                                )

                st.session_state.messages.append(
                    {"role": "assistant", "content": full_answer}
                )

    if st.session_state.messages:
        if st.button("Clear chat", type="secondary"):
            st.session_state.messages = []
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — TIMELINE
# ═══════════════════════════════════════════════════════════════════════════════

with tab_timeline:
    st.header("Activity Timeline")

    if event_count == 0:
        st.info(
            "No events extracted yet.\n\n"
            "Run `python scripts/run_ingest.py` to extract structured events from your notes."
        )
    else:
        col1, col2 = st.columns([2, 1])

        with col1:
            # ── Monthly activity chart ─────────────────────────────────────────
            monthly_df = analytics.monthly_activity()
            if not monthly_df.empty:
                st.subheader("Monthly activity by project")
                chart = (
                    alt.Chart(monthly_df)
                    .mark_bar()
                    .encode(
                        x=alt.X("month:O", title="Month", sort=None),
                        y=alt.Y("action_count:Q", title="Actions"),
                        color=alt.Color("project:N", legend=alt.Legend(title="Project")),
                        tooltip=["month", "project", "action_count"],
                    )
                    .properties(height=320)
                    .interactive()
                )
                st.altair_chart(chart, use_container_width=True)

        with col2:
            # ── Top projects ───────────────────────────────────────────────────
            top_df = analytics.top_projects(limit=10)
            if not top_df.empty:
                st.subheader("Top projects")
                st.dataframe(
                    top_df.rename(columns={
                        "project": "Project",
                        "action_count": "Actions",
                        "active_months": "Active months",
                    }),
                    hide_index=True,
                    use_container_width=True,
                )

        st.divider()

        # ── AI Summary ────────────────────────────────────────────────────────
        st.subheader("AI summary")
        year_options = ["All time"] + sorted(
            {m[:4] for m in (monthly_df["month"].tolist() if not monthly_df.empty else [])},
            reverse=True,
        )
        selected = st.selectbox("Summarize period:", year_options)

        if st.button("Generate summary", type="primary"):
            with st.spinner("Summarizing your activity..."):
                year = int(selected) if selected != "All time" else None
                summary = summarize_period(analytics, model=cfg.models.llm, year=year)
                st.markdown(summary)

        # ── Recent insights ────────────────────────────────────────────────────
        st.divider()
        st.subheader("Recent insights")
        insights_df = analytics.recent_insights(limit=15)
        if not insights_df.empty:
            for _, row in insights_df.iterrows():
                with st.container():
                    date_str = row.get("date") or "—"
                    project_str = row.get("project") or "—"
                    st.markdown(
                        f"**{date_str}** · _{project_str}_ · {row.get('insight', '')}"
                    )
        else:
            st.info("No insights recorded yet.")
