"""
Streamlit UI for the Research Agent.
Run: streamlit run app.py
"""

import asyncio
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agents import plan, search_and_summarize, write_report

st.set_page_config(page_title="Research Agent", page_icon="🔬", layout="wide")

st.title("🔬 Multi-Agent Research Assistant")
st.caption("Powered by a planner → parallel search agents → writer pipeline")

# Sidebar config
with st.sidebar:
    st.header("Configuration")
    st.markdown("""
**LLM Provider** — set in `.env`:
- `LLM_PROVIDER=groq` + `GROQ_API_KEY`
- `LLM_PROVIDER=ollama` (local)

**Search** — set in `.env`:
- `SERPER_API_KEY` for Serper
- Leave unset for DuckDuckGo (free)
    """)
    num_results = st.slider("Search results per question", 3, 8, 5)

topic = st.text_input(
    "Enter a research topic",
    placeholder="e.g. The impact of LLMs on software engineering jobs",
)

if st.button("🚀 Run Research", type="primary", disabled=not topic):
    with st.status("Running research pipeline...", expanded=True) as status:

        async def run():
            # Step 1: Plan
            st.write("🧠 **Planner** — decomposing topic into sub-questions...")
            sub_questions = await plan(topic)
            for i, q in enumerate(sub_questions, 1):
                st.write(f"  {i}. {q}")

            # Step 2: Parallel search
            st.write(f"\n📡 **Search agents** — running {len(sub_questions)} queries in parallel...")
            findings = await asyncio.gather(
                *[search_and_summarize(q, num_results=num_results) for q in sub_questions]
            )
            for f in findings:
                st.write(f"  ✓ `{f.question[:60]}...`")

            # Step 3: Write
            st.write("\n✍️  **Writer** — synthesising report...")
            report = await write_report(topic, list(findings))
            return report

        report = asyncio.run(run())
        status.update(label="✅ Research complete!", state="complete")

    st.divider()
    st.markdown(report)

    st.download_button(
        label="💾 Download report (.md)",
        data=report,
        file_name=f"{topic[:40].replace(' ', '_')}.md",
        mime="text/markdown",
    )
