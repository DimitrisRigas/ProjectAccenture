"""
src/governance/pii_redaction.py

Lightweight PII detection and redaction utilities.

This module is used before sending a user question to the RAG pipeline.
It redacts common sensitive patterns such as:
- email addresses
- phone numbers
- IBAN-like identifiers
- credit-card-like numbers

This is a lightweight governance control for the project demo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RedactionResult:
    original_text: str
    redacted_text: str
    redactions: dict[str, int]


PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
    "phone": re.compile(
        r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}\b"
    ),
    "iban": re.compile(
        r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
        re.IGNORECASE,
    ),
    "credit_card": re.compile(
        r"\b(?:\d[ -]*?){13,19}\b"
    ),
}


REPLACEMENTS: dict[str, str] = {
    "email": "[EMAIL_REDACTED]",
    "phone": "[PHONE_REDACTED]",
    "iban": "[IBAN_REDACTED]",
    "credit_card": "[CARD_REDACTED]",
}


def redact_pii(text: str) -> RedactionResult:
    """
    Redact common PII patterns from text.

    Parameters
    ----------
    text:
        Input text from the user.

    Returns
    -------
    RedactionResult:
        Original text, redacted text, and number of redactions by type.
    """

    redacted_text = text
    redactions: dict[str, int] = {}

    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(redacted_text)
        count = len(matches)

        if count > 0:
            redacted_text = pattern.sub(
                REPLACEMENTS[pii_type],
                redacted_text,
            )
            redactions[pii_type] = count
        else:
            redactions[pii_type] = 0

    return RedactionResult(
        original_text=text,
        redacted_text=redacted_text,
        redactions=redactions,
    )


def contains_pii(text: str) -> bool:
    """
    Return True if the text appears to contain common PII.
    """

    result = redact_pii(text)

    return any(
        count > 0
        for count in result.redactions.values()
    )


if __name__ == "__main__":
    sample = (
        "My email is test@example.com, my phone is +30 6912345678, "
        "and my IBAN is GR1601101250000000012300695. "
        "What does GDPR say about this?"
    )

    result = redact_pii(sample)

    print("Original:")
    print(result.original_text)
    print()

    print("Redacted:")
    print(result.redacted_text)
    print()

    print("Redactions:")
    print(result.redactions)