from __future__ import annotations

import re
from collections import Counter


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9+#.]+" )
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def tokenize(text: str) -> list[str]:
    tokens = [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]
    return [token for token in tokens if token not in STOPWORDS]


def term_frequency(text: str) -> Counter[str]:
    return Counter(tokenize(text))


def overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)


def bounded_score(value: float) -> float:
    return max(0.0, min(100.0, value))
