"""Content-based sensitivity labels for untagged data.

P1: deterministic keyword/regex rules. P3 adds Presidio and a local model as extra
layers. Labels are only ever ADDED by content, never removed, so text inside the data
cannot downgrade its own sensitivity.
"""
from __future__ import annotations

import re

PATTERNS: dict[str, list[str]] = {
    "financial": [
        r"\bloans?\b", r"mortgage", r"\bbank(ing)?\b", r"barclays", r"hsbc", r"lloyds",
        r"monzo", r"natwest", r"credit card", r"\b(card|account) ending\b", r"payslips?",
        r"£\s?\d", r"\binvoice\b", r"\btax(es)?\b", r"\bsalary\b", r"\bbalance\b",
    ],
    "health": [
        r"physio", r"dentist", r"doctor", r"\bgp\b", r"therap(y|ist)", r"hospital",
        r"clinic", r"prescription", r"rehab", r"counsell?ing", r"\bmedical\b",
    ],
    "location": [
        r"\baddress\b", r"\b\d+\s+\w+\s+(road|street|st|avenue|ave|lane|close|drive)\b",
    ],
    "credentials": [r"password", r"passport", r"\bpin\b", r"\bssn\b"],
    "people": [r"[\w.+-]+@[\w-]+\.[\w.]+", r"\+?\d[\d\s]{9,}\d"],
}

_COMPILED = {cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in PATTERNS.items()}


def classify_text(text: str) -> set[str]:
    if not text:
        return set()
    return {cat for cat, regs in _COMPILED.items() if any(r.search(text) for r in regs)}
