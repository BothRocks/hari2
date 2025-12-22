import enum


class QualityGrade(str, enum.Enum):
    """Quality grade for document scoring."""

    A = "A"  # 90+
    B = "B"  # 70-89
    C = "C"  # 50-69
    D = "D"  # <50


def calculate_quality_score(
    summary: str | None = None,
    quick_summary: str | None = None,
    keywords: list[str] | None = None,
    industries: list[str] | None = None,
    has_embedding: bool = False,
) -> float:
    """Calculate quality score (0-100) for a document.

    Args:
        summary: Main document summary
        quick_summary: Brief summary
        keywords: List of keywords
        industries: List of industries
        has_embedding: Whether document has an embedding

    Returns:
        Quality score between 0 and 100

    Scoring breakdown:
        - Summary quality: 40% (optimal: 800-2500 chars)
        - Quick summary: 10% (minimum: 50 chars)
        - Keywords: 15% (optimal: 5-10 items)
        - Industries: 15% (at least one)
        - Embedding: 20% (present or not)
    """
    score = 0.0

    # Summary quality (40%)
    if summary:
        length = len(summary)
        if 800 <= length <= 2500:
            score += 40
        elif 400 <= length < 800 or 2500 < length <= 4000:
            score += 30
        elif length > 0:
            score += 15

    # Quick summary (10%)
    if quick_summary and len(quick_summary) >= 50:
        score += 10

    # Metadata quality (30%)
    # Keywords (15%)
    if keywords:
        keyword_count = len(keywords)
        if 5 <= keyword_count <= 10:
            score += 15
        elif keyword_count > 0:
            score += 8

    # Industries (15%)
    if industries:
        score += 15

    # Technical quality (20%)
    if has_embedding:
        score += 20

    return min(score, 100.0)


def get_grade(score: float) -> QualityGrade:
    """Convert score to grade.

    Args:
        score: Quality score between 0 and 100

    Returns:
        QualityGrade corresponding to the score
    """
    if score >= 90:
        return QualityGrade.A
    elif score >= 70:
        return QualityGrade.B
    elif score >= 50:
        return QualityGrade.C
    else:
        return QualityGrade.D
