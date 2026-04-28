"""
tests/test_splitter.py
Unit tests for loader and splitter — no Ollama or DB needed.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingest.loader import _load_markdown, RawDocument
from src.ingest.splitter import split_documents
from src.extract.schema import Event


# ── Splitter tests ────────────────────────────────────────────────────────────

def _make_doc(content: str, doc_id: str = "test01") -> RawDocument:
    return RawDocument(
        doc_id=doc_id,
        source_path="test/page.md",
        title="Test Page",
        content=content,
    )


def test_split_short_text():
    doc = _make_doc("Hello world. This is a short note.")
    chunks = split_documents([doc], chunk_size=500)
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world. This is a short note."
    assert chunks[0].doc_id == "test01"
    assert chunks[0].source_path == "test/page.md"


def test_split_long_text():
    doc = _make_doc("Word " * 300)  # 1500 chars
    chunks = split_documents([doc], chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 220  # slight tolerance for overlap


def test_chunk_ids_are_unique():
    doc = _make_doc("Word " * 300)
    chunks = split_documents([doc], chunk_size=200)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_carries_metadata():
    doc = _make_doc("Some content", doc_id="abc123")
    doc.metadata["type"] = "journal"
    chunks = split_documents([doc])
    assert chunks[0].metadata.get("type") == "journal"


# ── Event schema tests ────────────────────────────────────────────────────────

def test_event_valid():
    e = Event(
        date="2024-03-15",
        project="Website redesign",
        action="Built the navigation component",
        source_page="projects/website.md",
    )
    assert e.date == "2024-03-15"
    assert e.project == "Website redesign"


def test_event_bad_date_becomes_none():
    e = Event(
        date="March 2024",  # unparseable
        action="Did something",
        source_page="notes/page.md",
    )
    assert e.date is None


def test_event_null_strings_become_none():
    e = Event(
        date=None,
        project="null",  # LLM output of "null"
        topic="n/a",
        action="Wrote tests",
        source_page="tests/test.md",
    )
    assert e.project is None
    assert e.topic is None


def test_event_empty_action_raises():
    with pytest.raises(Exception):
        Event(action="", source_page="some/page.md")


def test_event_empty_source_raises():
    with pytest.raises(Exception):
        Event(action="Did something", source_page="")
