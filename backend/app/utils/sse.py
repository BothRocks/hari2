"""SSE (Server-Sent Events) formatting utilities."""
import json
from typing import Any, Iterator


# Common abbreviations that don't end sentences
# Note: Multi-part abbreviations like "e.g." and "i.e." are not handled
ABBREVIATIONS = {"Dr", "Mr", "Mrs", "Ms", "Prof", "Sr", "Jr", "vs", "etc"}


def chunk_sentences(text: str) -> Iterator[str]:
    """
    Split text into sentence chunks.

    Args:
        text: Text to split

    Yields:
        Individual sentences with trailing space preserved
    """
    if not text:
        return

    # Find all potential sentence boundaries (. ! ? followed by space)
    # Then filter out those that are abbreviations
    current_start = 0
    i = 0
    while i < len(text):
        # Look for sentence-ending punctuation followed by space or end of string
        if text[i] in ".!?" and (i + 1 >= len(text) or text[i + 1] == " "):
            # Check if this is an abbreviation
            is_abbreviation = False
            if text[i] == ".":
                # Find the word before the period
                word_start = i - 1
                while word_start >= current_start and text[word_start].isalpha():
                    word_start -= 1
                word_start += 1
                word = text[word_start:i]
                if word in ABBREVIATIONS:
                    is_abbreviation = True

            if not is_abbreviation:
                # This is a sentence boundary
                if i + 1 < len(text) and text[i + 1] == " ":
                    # Include the space after punctuation, yield with trailing space
                    yield text[current_start : i + 1] + " "
                    current_start = i + 2
                    i = current_start
                    continue
                else:
                    # End of string - yield without trailing space
                    yield text[current_start : i + 1]
                    current_start = i + 1
        i += 1

    # Yield any remaining text
    if current_start < len(text):
        yield text[current_start:]


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    """
    Format data as an SSE event string.

    Args:
        event_type: Event type (thinking, chunk, sources, done, error)
        data: Event data dictionary

    Returns:
        SSE-formatted string with event and data lines
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def parse_sse(raw: str) -> list[dict[str, Any]]:
    """
    Parse raw SSE text into list of events.

    Args:
        raw: Raw SSE text (may contain multiple events)

    Returns:
        List of parsed events with 'type' and 'data' keys
    """
    events = []
    current_event = {}

    for line in raw.split("\n"):
        if line.startswith("event: "):
            current_event["type"] = line[7:]
        elif line.startswith("data: "):
            try:
                current_event["data"] = json.loads(line[6:])
            except json.JSONDecodeError:
                current_event["data"] = line[6:]
        elif line == "" and current_event:
            if "type" in current_event and "data" in current_event:
                events.append(current_event)
            current_event = {}

    return events
