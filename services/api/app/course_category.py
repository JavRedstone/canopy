"""Server-side port of apps/web/lib/course-category.ts's keyword heuristic, plus the
accent-color pairing used for the "download coursebook" banner in course-detail.tsx.

Kept as a small, deliberately duplicated lookup table (not shared code across the
TS/Python boundary) so the certificate -- issued as both a PDF and a web view -- can
theme itself from a *single, server-computed* value instead of running the heuristic
twice and risking the two disagreeing."""

from __future__ import annotations

_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("security", ["security", "auth", "jwt", "oauth", "encryption", "vulnerability", "penetration"]),
    ("ml", ["machine learning", " ml ", "neural", "deep learning", "supervised", "unsupervised", "llm", "artificial intelligence", " ai "]),
    ("data", ["sql", "database", "data engineering", "postgres", "etl", "pipeline", "warehouse"]),
    ("web", ["web", "react", "frontend", "html", "css", "next.js", "javascript", "typescript", "dom"]),
    ("backend", ["api", "backend", "server", "fastapi", "django", "microservice", "rest"]),
    ("cloud", ["cloud", "docker", "kubernetes", "aws", "azure", "devops", "deployment", "infrastructure"]),
    ("code", ["python", "programming", "algorithm", "code", "software", "language"]),
]

# Dark accent (headings/border) + a light tint of the same hue (chip backgrounds) per
# category. The accent values are exactly course-detail.tsx's `coursebookAccentColors`,
# so a certificate and that course's own coursebook banner always match.
_ACCENT_COLORS: dict[str, str] = {
    "security": "#581c27", "ml": "#312e81", "data": "#78350f", "web": "#0c4a6e",
    "backend": "#14532d", "cloud": "#134e4a", "code": "#365314", "default": "#334155",
}
_TINT_COLORS: dict[str, str] = {
    "security": "#fee2e2", "ml": "#eef2ff", "data": "#fef3c7", "web": "#dbeafe",
    "backend": "#dcfce7", "cloud": "#ccfbf1", "code": "#ecfccb", "default": "#f1f5f9",
}


def category_for(title: str, goal: str) -> str:
    haystack = f" {title.lower()} {goal.lower()} "
    for key, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return key
    return "default"


def accent_colors_for(title: str, goal: str) -> tuple[str, str]:
    """(accent, tint) hex pair for this course's category."""
    category = category_for(title, goal)
    return _ACCENT_COLORS[category], _TINT_COLORS[category]
