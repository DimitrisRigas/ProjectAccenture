"""
src/regulatory_corpus.py

Registry of regulatory documents to ingest.

EUR-Lex documents are identified by CELEX ID only — title and file name
are derived automatically. Metadata is fetched from CELLAR at download time.

Non-CELEX documents (EBA, ECB) include full configuration since they
cannot be discovered via the CELLAR API.

To add a new EUR-Lex document, append a single dict with celex,
short_title, and category. Nothing else needs to change.
"""

from __future__ import annotations

EUR_LEX_DOCUMENTS: list[dict] = [
    {
        "celex": "32016R0679",
        "short_title": "GDPR",
        "category": "Data Protection",
    },
    {
        "celex": "32022R2554",
        "short_title": "DORA",
        "category": "Digital Finance",
    },
    {
        "celex": "32015L2366",
        "short_title": "PSD2",
        "category": "Payments",
    },
    {
        "celex": "32014L0065",
        "short_title": "MiFID_II",
        "category": "Financial Markets",
    },
    {
        "celex": "32024R1689",
        "short_title": "AI_Act",
        "category": "Artificial Intelligence",
    },
]

WEB_DOCUMENTS: list[dict] = [
    {
        "document_id": "eba_loan_origination_guidelines_html",
        "short_title": "EBA_Loan_Origination",
        "title": "EBA Guidelines on Loan Origination and Monitoring",
        "category": "Credit Risk",
        "source_system": "EBA",
        "source_url": (
            "https://www.eba.europa.eu/activities/single-rulebook/"
            "regulatory-activities/credit-risk/"
            "guidelines-loan-origination-and-monitoring"
        ),
        "file_format": "html",
        "file_name": "eba_loan_origination_guidelines_html.html",
    },
    {
        "document_id": "ecb_eurofxref_daily_xml",
        "short_title": "ECB_Exchange_Rates",
        "title": "ECB Euro Foreign Exchange Reference Rates",
        "category": "Financial Markets",
        "source_system": "ECB",
        "source_url": "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
        "file_format": "xml",
        "file_name": "ecb_eurofxref_daily_xml.xml",
    },
]