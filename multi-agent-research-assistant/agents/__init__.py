"""
Agents package initializer.

Re-export the main agent entrypoints so top-level scripts can import them as:

    from agents import plan, search_and_summarize, write_report
"""

from .planner import plan
from .searcher import search_and_summarize
from .writer import write_report

__all__ = ["plan", "search_and_summarize", "write_report"]
