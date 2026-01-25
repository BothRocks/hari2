# backend/app/agent/utils.py
"""Utility functions for the agent."""
from datetime import date


def get_date_context() -> str:
    """
    Get current date context for LLM prompts.

    Returns:
        Date string like "Today's date is January 25, 2026. "
    """
    today = date.today()
    return f"Today's date is {today.strftime('%B %d, %Y')}. "
