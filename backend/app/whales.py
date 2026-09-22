"""Curated list of significant institutional investors ("whales").

CIK values are SEC EDGAR Central Index Keys for each fund's 13F filer entity.
These should be verified against https://www.sec.gov/cgi-bin/browse-edgar if a
whale consistently returns no filings.
"""

from __future__ import annotations

# Mapping of SEC CIK -> human readable whale name.
FAMOUS_WHALES: dict[str, str] = {
    "0001067983": "Berkshire Hathaway (Warren Buffett)",
    "0001649339": "Scion Asset Management (Michael Burry)",
    "0001336528": "Pershing Square (Bill Ackman)",
    "0001350694": "Bridgewater Associates (Ray Dalio)",
    "0001037389": "Renaissance Technologies",
    "0001061768": "Baupost Group (Seth Klarman)",
    "0001040273": "Third Point (Dan Loeb)",
    "0001536411": "Duquesne Family Office (Stanley Druckenmiller)",
    "0001079114": "Greenlight Capital (David Einhorn)",
    "0001029160": "Soros Fund Management",
    "0001167483": "Tiger Global Management",
    "0001423053": "Citadel Advisors",
    "0001179392": "Two Sigma Investments",
    "0001273087": "Millennium Management",
    "0001103804": "Viking Global Investors",
}


def normalize_cik(cik: str) -> str:
    """Return a CIK in the zero-padded 10-digit form used as dict keys."""
    digits = cik.strip().lstrip("0")
    if digits.isdigit():
        return digits.zfill(10)
    return cik.strip()


def whale_name(cik: str) -> str:
    """Return the friendly name for a whale CIK, falling back to the CIK itself."""
    return FAMOUS_WHALES.get(normalize_cik(cik), cik)
