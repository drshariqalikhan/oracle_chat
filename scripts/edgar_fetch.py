#!/usr/bin/env python3
"""
Standalone SEC EDGAR data fetcher (no AI / no external market scrapers).

Usage:
    python3 scripts/edgar_fetch.py NVDA
    python3 scripts/edgar_fetch.py WMT
    python3 scripts/edgar_fetch.py AAPL
"""

import json
import os
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "OracleChatEdgarFetcher/1.0 (contact@example.com)",
).strip()
TIMEOUT = 20

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}"

GUIDANCE_HEADINGS = (
    "financial outlook",
    "fiscal year outlook",
    "business outlook",
    "financial guidance",
    "company outlook",
    "guidance",
    "outlook",
)

STOP_HEADINGS = (
    "conference call",
    "webcast",
    "about ",
    "forward-looking statements",
    "forward looking statements",
    "safe harbor",
    "non-gaap",
    "reconciliation",
    "consolidated statements",
    "balance sheet",
    "share repurchase",
)

BUSINESS_FACT_METRICS = (
    "vehicles delivered",
    "restaurants",
    "stores",
    "locations",
    "subscribers",
    "members",
    "rooms",
    "customers",
)

BUSINESS_FACT_ADJECTIVES = (
    r"(?:(?:retail|company-operated|company-owned|franchised|owned|total|active|"
    r"paid|global|worldwide|domestic|international|new|net|approximate|approximately)\s+){0,2}"
)

SCALE_MULTIPLIERS = {
    "trillion": 1_000_000_000_000.0,
    "billion": 1_000_000_000.0,
    "b": 1_000_000_000.0,
    "million": 1_000_000.0,
    "m": 1_000_000.0,
    "thousand": 1_000.0,
}


def make_sec_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json, text/html, */*",
        }
    )
    return session


def sec_get_json(session: requests.Session, url: str) -> Any | None:
    time.sleep(0.12)
    try:
        resp = session.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"[WARN] SEC GET {url} -> HTTP {resp.status_code}", file=sys.stderr)
            return None
        return resp.json()
    except Exception as exc:
        print(f"[WARN] SEC request error for {url}: {exc}", file=sys.stderr)
        return None


def sec_get_text(session: requests.Session, url: str, max_bytes: int = 8 * 1024 * 1024) -> str | None:
    time.sleep(0.12)
    try:
        resp = session.get(url, timeout=TIMEOUT, stream=True)
        if resp.status_code != 200:
            print(f"[WARN] SEC GET {url} -> HTTP {resp.status_code}", file=sys.stderr)
            return None
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= max_bytes:
                break
        return b"".join(chunks).decode("utf-8", errors="ignore")
    except Exception as exc:
        print(f"[WARN] SEC download error for {url}: {exc}", file=sys.stderr)
        return None


def lookup_cik(session: requests.Session, ticker: str) -> tuple[str | None, str | None]:
    data = sec_get_json(session, SEC_TICKERS_URL)
    if not isinstance(data, dict):
        return None, None
    target = ticker.strip().upper()
    for entry in data.values():
        if isinstance(entry, dict) and str(entry.get("ticker", "")).strip().upper() == target:
            cik10 = f"{int(entry['cik_str']):010d}"
            title = str(entry.get("title", "")).strip() or None
            return cik10, title
    return None, None


def find_latest_filings(submissions: dict[str, Any]) -> dict[str, dict[str, str] | None]:
    out: dict[str, dict[str, str] | None] = {"8-K": None, "10-K": None, "10-Q": None}
    recent = (submissions.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accs = recent.get("accessionNumber") or []
    docs = recent.get("primaryDocument") or []
    items_list = recent.get("items") or []

    fallback_8k: dict[str, str] | None = None

    for idx, form in enumerate(forms):
        form_upper = str(form).strip().upper()
        acc = str(accs[idx]) if idx < len(accs) else ""
        doc = str(docs[idx]) if idx < len(docs) else ""
        fdate = str(dates[idx]) if idx < len(dates) else ""
        raw_items = items_list[idx] if idx < len(items_list) else ""
        items = ",".join(str(x) for x in raw_items) if isinstance(raw_items, list) else str(raw_items)
        if not acc:
            continue

        record = {
            "form": form_upper,
            "filingDate": fdate,
            "accessionNumber": acc,
            "primaryDocument": doc,
            "items": items,
        }

        if form_upper == "8-K":
            if fallback_8k is None:
                fallback_8k = record
            if out["8-K"] is None and ("2.02" in items or not items_list):
                out["8-K"] = record
        elif form_upper == "10-K" and out["10-K"] is None:
            out["10-K"] = record
        elif form_upper == "10-Q" and out["10-Q"] is None:
            out["10-Q"] = record

        if out["8-K"] and out["10-K"] and out["10-Q"]:
            break

    if out["8-K"] is None:
        out["8-K"] = fallback_8k
    return out


def _find_exhibit_99_from_index_html(
    session: requests.Session,
    base_url: str,
    accession_number: str,
) -> str | None:
    index_url = f"{base_url}/{accession_number}-index.htm"
    index_html = sec_get_text(session, index_url, max_bytes=1024 * 1024)
    if not index_html:
        return None

    soup = BeautifulSoup(index_html, "lxml")
    candidates: list[tuple[int, str]] = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        doc_type = cells[3].get_text(" ", strip=True).upper()
        link = cells[2].find("a", href=True)
        if not link:
            continue
        href = str(link["href"]).strip()
        filename = href.split("/")[-1].split("?")[0]
        lower_name = filename.lower()
        if not (lower_name.endswith(".htm") or lower_name.endswith(".html")):
            continue

        if doc_type in ("EX-99.1", "EX-99"):
            candidates.append((0, filename))
        elif doc_type.startswith("EX-99"):
            candidates.append((1, filename))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def download_filing_html(
    session: requests.Session,
    cik10: str,
    filing: dict[str, str] | None,
    prefer_exhibit_99: bool = False,
) -> tuple[str | None, str | None]:
    if not filing or not filing.get("accessionNumber"):
        return None, None

    acc = filing["accessionNumber"]
    cik_int = str(int(cik10))
    acc_nodash = acc.replace("-", "")
    base_url = SEC_ARCHIVE_BASE.format(cik_int=cik_int, acc_nodash=acc_nodash)

    if prefer_exhibit_99:
        # 1. Most reliable: parse SEC's official {acc}-index.htm table for Type == EX-99.1
        ex99_filename = _find_exhibit_99_from_index_html(session, base_url, acc)
        if ex99_filename:
            ex99_url = f"{base_url}/{ex99_filename}"
            html = sec_get_text(session, ex99_url)
            if html and len(html) > 300:
                return html, ex99_url

        # 2. Fallback: scan index.json filenames
        index_data = sec_get_json(session, f"{base_url}/index.json")
        items = ((index_data or {}).get("directory") or {}).get("item") or []
        primary_doc_lower = filing.get("primaryDocument", "").lower()
        candidates: list[str] = []
        for item in items:
            name = str(item.get("name", ""))
            lower = name.lower()
            if not (lower.endswith(".htm") or lower.endswith(".html")):
                continue
            if "index" in lower or lower == primary_doc_lower:
                continue
            if any(tag in lower for tag in ("99", "release", "earnings", "pr")):
                candidates.append(name)

        candidates.sort(key=lambda n: (0 if "99" in n.lower() else 1, len(n)))
        for candidate in candidates:
            url = f"{base_url}/{candidate}"
            html = sec_get_text(session, url)
            if html and len(html) > 300:
                return html, url

    primary_doc = filing.get("primaryDocument", "")
    if primary_doc:
        url = f"{base_url}/{primary_doc}"
        return sec_get_text(session, url), url
    return None, None


# ---------------------------------------------------------------------------
# SEC XBRL CompanyFacts Extraction
# ---------------------------------------------------------------------------
def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _duration_days(point: dict[str, Any]) -> int | None:
    start = _parse_date(point.get("start"))
    end = _parse_date(point.get("end"))
    if not start or not end:
        return None
    return (end - start).days


def _dedupe_by_end_date(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_end: dict[str, dict[str, Any]] = {}
    for p in points:
        end = str(p.get("end", ""))
        if not end or p.get("val") is None:
            continue
        existing = by_end.get(end)
        if not existing or str(p.get("filed", "")) >= str(existing.get("filed", "")):
            by_end[end] = p
    return sorted(by_end.values(), key=lambda x: str(x.get("end", "")), reverse=True)


def _get_merged_fact_points(namespace: dict[str, Any], tags: list[str], unit: str) -> list[dict[str, Any]]:
    """Collect points across all tag aliases so newer filings using an updated tag aren't shadowed."""
    merged: list[dict[str, Any]] = []
    for tag in tags:
        concept = namespace.get(tag)
        if not isinstance(concept, dict):
            continue
        units = concept.get("units") or {}
        if unit in units and isinstance(units[unit], list):
            merged.extend(units[unit])
            continue
        for u_key, u_vals in units.items():
            if u_key.lower() == unit.lower() and isinstance(u_vals, list):
                merged.extend(u_vals)
                break
    return merged


def _select_annual_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annual = [
        p
        for p in points
        if p.get("form") in ("10-K", "10-K/A")
        and ((_duration_days(p) is None) or (330 <= (_duration_days(p) or 0) <= 385))
    ]
    return _dedupe_by_end_date(annual)


def _select_quarterly_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    quarterly = [
        p
        for p in points
        if p.get("form") in ("10-Q", "10-Q/A", "10-K", "10-K/A")
        and ((_duration_days(p) is not None) and (70 <= (_duration_days(p) or 0) <= 110))
    ]
    return _dedupe_by_end_date(quarterly)


def _latest_val(namespace: dict[str, Any], tags: list[str], unit: str) -> float | None:
    pts = _dedupe_by_end_date(_get_merged_fact_points(namespace, tags, unit))
    return _to_float(pts[0].get("val")) if pts else None


def extract_xbrl_metrics(company_facts: dict[str, Any] | None) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {
        "revenue_annual": None,
        "revenue_yoy": None,
        "revenue_quarterly": None,
        "eps_annual_gaap": None,
        "eps_gaap_quarterly": None,
        "shares_outstanding": None,
        "cash": None,
        "total_debt": None,
        "net_debt": None,
        "dividend_annual": None,
    }
    if not company_facts:
        return metrics

    facts = company_facts.get("facts") or {}
    us_gaap = facts.get("us-gaap") or {}
    dei = facts.get("dei") or {}

    rev_points = _get_merged_fact_points(
        us_gaap,
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
        "USD",
    )
    annual_revs = _select_annual_points(rev_points)
    if annual_revs:
        metrics["revenue_annual"] = _to_float(annual_revs[0].get("val"))
        if len(annual_revs) >= 2:
            prev_rev = _to_float(annual_revs[1].get("val"))
            if metrics["revenue_annual"] is not None and prev_rev and prev_rev != 0:
                metrics["revenue_yoy"] = round(
                    ((metrics["revenue_annual"] - prev_rev) / abs(prev_rev)) * 100.0,
                    2,
                )

    quarterly_revs = _select_quarterly_points(rev_points)
    if quarterly_revs:
        metrics["revenue_quarterly"] = _to_float(quarterly_revs[0].get("val"))

    eps_points = _get_merged_fact_points(us_gaap, ["EarningsPerShareDiluted"], "USD/shares")
    annual_eps = _select_annual_points(eps_points)
    if annual_eps:
        metrics["eps_annual_gaap"] = _to_float(annual_eps[0].get("val"))
    quarterly_eps = _select_quarterly_points(eps_points)
    if quarterly_eps:
        metrics["eps_gaap_quarterly"] = _to_float(quarterly_eps[0].get("val"))

    shares = _latest_val(dei, ["EntityCommonStockSharesOutstanding"], "shares")
    if shares is None:
        shares = _latest_val(
            us_gaap,
            ["CommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding"],
            "shares",
        )
    metrics["shares_outstanding"] = shares

    cash = _latest_val(
        us_gaap,
        [
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ],
        "USD",
    )
    metrics["cash"] = cash

    lt_debt = _latest_val(us_gaap, ["LongTermDebt"], "USD")
    lt_noncurrent = _latest_val(us_gaap, ["LongTermDebtNoncurrent"], "USD")
    lt_current = _latest_val(us_gaap, ["CurrentPortionOfLongTermDebt", "LongTermDebtCurrent"], "USD")
    st_borrowings = _latest_val(us_gaap, ["ShortTermBorrowings"], "USD")

    total_debt: float | None = None
    if lt_noncurrent is not None:
        total_debt = lt_noncurrent + (lt_current or 0.0) + (st_borrowings or 0.0)
    elif lt_debt is not None:
        total_debt = lt_debt + (st_borrowings or 0.0)
    elif lt_current is not None or st_borrowings is not None:
        total_debt = (lt_current or 0.0) + (st_borrowings or 0.0)

    metrics["total_debt"] = total_debt
    if total_debt is not None and cash is not None:
        metrics["net_debt"] = round(total_debt - cash, 2)

    div_points = _get_merged_fact_points(
        us_gaap,
        ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"],
        "USD/shares",
    )
    annual_divs = _select_annual_points(div_points)
    if annual_divs:
        metrics["dividend_annual"] = _to_float(annual_divs[0].get("val"))
    else:
        q_divs = _select_quarterly_points(div_points)
        if q_divs:
            metrics["dividend_annual"] = round(
                sum(float(p["val"]) for p in q_divs[:4] if p.get("val") is not None),
                4,
            )

    return metrics


# ---------------------------------------------------------------------------
# HTML Parsing (8-K / 10-K) — Rule-Based Only (No AI)
# ---------------------------------------------------------------------------
def html_to_blocks(html: str) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    blocks: list[str] = []
    container_tags = ["div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol"]
    block_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "div", "tr"])
    if block_tags:
        seen: set[str] = set()
        for el in block_tags:
            if el.name == "div" and el.find(container_tags):
                continue
            if el.name == "tr" and el.find(["p", "div", "table"]):
                continue
            text = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
            if text and text not in seen:
                seen.add(text)
                blocks.append(text)
    else:
        raw_lines = soup.get_text("\n", strip=True).splitlines()
        blocks = [re.sub(r"\s+", " ", line).strip() for line in raw_lines if line.strip()]
    return blocks


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])", cleaned)
    return [p.strip() for p in parts if p.strip()]


def _parse_scaled_money(number_str: str, unit_str: str | None) -> float | None:
    try:
        base = float(number_str.replace(",", "").strip())
    except ValueError:
        return None
    if unit_str:
        mult = SCALE_MULTIPLIERS.get(unit_str.strip().lower(), 1.0)
        return round(base * mult, 2)
    return base


def extract_revenue_latest(text: str) -> float | None:
    patterns = [
        re.compile(
            r"(?:total\s+)?(?:quarterly\s+)?(?:revenue|net\s+sales|net\s+revenue)s?\s+"
            r"(?:of|was|totaled|reached|rose\s+to|increased\s+to|grew\s+to|declined\s+to)?\s*"
            r"\$\s*([\d,]+(?:\.\d+)?)\s*(trillion|billion|million|thousand|B|M)?\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\$\s*([\d,]+(?:\.\d+)?)\s*(trillion|billion|million)\b[^.]{0,60}?"
            r"\b(?:in\s+)?(?:quarterly\s+)?(?:revenue|net\s+sales)\b",
            re.IGNORECASE,
        ),
    ]
    for pat in patterns:
        m = pat.search(text)
        if m:
            val = _parse_scaled_money(m.group(1), m.group(2))
            if val is not None and val >= 1_000_000:
                return val
    return None


def extract_eps_values(text: str) -> tuple[float | None, float | None]:
    eps_gaap: float | None = None
    eps_non_gaap: float | None = None

    for pat in (
        re.compile(
            r"(?:non-GAAP|adjusted)\s+(?:diluted\s+)?(?:earnings\s+per\s+(?:diluted\s+)?share|EPS)\s*"
            r"(?:of|was|were|:)?\s*\$?\s*(-?\d+\.\d{2})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:diluted\s+)?(?:earnings\s+per\s+share|EPS)\s+on\s+a\s+(?:non-GAAP|adjusted)\s+basis\s+"
            r"(?:of|was|were)?\s*\$?\s*(-?\d+\.\d{2})",
            re.IGNORECASE,
        ),
    ):
        m = pat.search(text)
        if m:
            eps_non_gaap = _to_float(m.group(1))
            if eps_non_gaap is not None:
                break

    for pat in (
        re.compile(
            r"GAAP\s+(?:diluted\s+)?(?:earnings\s+per\s+(?:diluted\s+)?share|EPS)\s*"
            r"(?:of|was|were|:)?\s*\$?\s*(-?\d+\.\d{2})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:diluted\s+earnings\s+per\s+share|earnings\s+per\s+diluted\s+share|"
            r"quarterly\s+earnings\s+per\s+diluted\s+share|diluted\s+EPS)\s*"
            r"(?:of|was|were|:)?\s*\$?\s*(-?\d+\.\d{2})",
            re.IGNORECASE,
        ),
    ):
        m = pat.search(text)
        if m:
            prefix = text[max(0, m.start() - 20) : m.start()].lower()
            if "non-gaap" in prefix or "adjusted" in prefix:
                continue
            eps_gaap = _to_float(m.group(1))
            if eps_gaap is not None:
                break

    return eps_gaap, eps_non_gaap


def extract_comps(text: str) -> dict[str, str]:
    comps: dict[str, str] = {}
    comp_terms = ("comparable sales", "comp sales", "same-store sales", "same store sales")
    for sent in _split_sentences(text):
        lower = sent.lower()
        for term in comp_terms:
            if term in lower:
                m = re.search(
                    r"(increased|decreased|grew|rose|declined|fell|up|down)?\s*([+-]?\d+(?:\.\d+)?%)",
                    sent,
                    re.IGNORECASE,
                )
                key = term.replace("-", "_").replace(" ", "_")
                if m:
                    direction = (m.group(1) or "").strip()
                    comps[key] = f"{direction} {m.group(2).strip()}".strip()
                else:
                    comps[key] = sent[:240]
                break
    return comps


def extract_margin_line(text: str) -> str | None:
    sentences = _split_sentences(text)
    for sent in sentences:
        lower = sent.lower()
        if any(term in lower for term in ("gross margin", "operating margin", "margin")):
            if any(ch.isdigit() for ch in sent) or "%" in sent or "basis point" in lower:
                return sent
    for sent in sentences:
        if "margin" in sent.lower():
            return sent
    return None


def extract_guidance_text(blocks: list[str]) -> str | None:
    for idx, block in enumerate(blocks):
        cleaned = block.strip()
        lower = cleaned.lower().rstrip(":")

        if "forward-looking" in lower or "safe harbor" in lower:
            continue

        is_heading = len(cleaned) <= 100 and (
            any(lower == h or lower.endswith(h) or lower.startswith(h) for h in GUIDANCE_HEADINGS)
            or bool(re.search(r"\b(?:guidance|outlook)\b", lower))
        )
        if is_heading and not any(cleaned.endswith(p) for p in (".", "!", "?")):
            collected: list[str] = []
            for next_block in blocks[idx + 1 : idx + 8]:
                next_lower = next_block.lower().strip()
                if len(next_block) <= 75 and any(next_lower.startswith(s) for s in STOP_HEADINGS):
                    break
                if len(next_block) >= 25:
                    collected.append(next_block)
                    if len(" ".join(collected)) >= 900:
                        break
            if collected:
                return "\n\n".join(collected)

        inline_match = re.match(
            r"^(?:[A-Za-z0-9\s]{0,35})?(?:Financial\s+Outlook|Fiscal\s+Year\s+Outlook|"
            r"Business\s+Outlook|Financial\s+Guidance|Guidance|Outlook)\s*[:\-]\s*(.+)$",
            cleaned,
            re.IGNORECASE,
        )
        if inline_match and len(inline_match.group(1).strip()) >= 25:
            return inline_match.group(1).strip()

    return None


def extract_business_fact(text: str) -> dict[str, Any] | None:
    for metric in BUSINESS_FACT_METRICS:
        pattern = re.compile(
            rf"\b([\d,]+(?:\.\d+)?)\s*(million|billion|thousand)?\s*{BUSINESS_FACT_ADJECTIVES}{re.escape(metric)}\b",
            re.IGNORECASE,
        )
        m = pattern.search(text)
        if m:
            val = _parse_scaled_money(m.group(1), m.group(2))
            if val is not None and val > 0:
                return {
                    "metric_name": metric,
                    "metric_value": int(val) if val.is_integer() else val,
                }
    return None


def fetch_edgar_summary(ticker: str, show_headings: bool = False) -> dict[str, Any]:
    symbol = ticker.strip().upper()
    session = make_sec_session()

    cik10, company_name = lookup_cik(session, symbol)
    if not cik10:
        return {
            "ticker": symbol,
            "cik": None,
            "company_name": None,
            "error": f"Ticker '{symbol}' not found in SEC EDGAR.",
        }

    company_facts = sec_get_json(session, SEC_COMPANY_FACTS_URL.format(cik=cik10))
    xbrl = extract_xbrl_metrics(company_facts)

    submissions = sec_get_json(session, SEC_SUBMISSIONS_URL.format(cik=cik10))
    filings = find_latest_filings(submissions) if submissions else {"8-K": None, "10-K": None, "10-Q": None}

    html_8k, url_8k = download_filing_html(session, cik10, filings.get("8-K"), prefer_exhibit_99=True)
    blocks_8k = html_to_blocks(html_8k or "")
    text_8k = "\n".join(blocks_8k)

    business_fact = extract_business_fact(text_8k) if text_8k else None
    if business_fact is None:
        fallback_filing = filings.get("10-K") or filings.get("10-Q")
        html_10, _ = download_filing_html(session, cik10, fallback_filing, prefer_exhibit_99=False)
        if html_10:
            business_fact = extract_business_fact("\n".join(html_to_blocks(html_10)))

    eps_gaap_8k, eps_non_gaap_8k = extract_eps_values(text_8k) if text_8k else (None, None)
    revenue_8k = extract_revenue_latest(text_8k) if text_8k else None

    out: dict[str, Any] = {
        "ticker": symbol,
        "cik": cik10,
        "company_name": company_name,
        "filings": {
            "latest_8k_date": (filings.get("8-K") or {}).get("filingDate"),
            "latest_8k_items": (filings.get("8-K") or {}).get("items"),
            "latest_8k_url": url_8k,
            "blocks_extracted": len(blocks_8k),
            "latest_10k_date": (filings.get("10-K") or {}).get("filingDate"),
            "latest_10q_date": (filings.get("10-Q") or {}).get("filingDate"),
        },
        "latest_earnings_8k": {
            "revenue_latest": revenue_8k or xbrl.get("revenue_quarterly"),
            "eps_gaap_latest": eps_gaap_8k or xbrl.get("eps_gaap_quarterly"),
            "eps_non_gaap_latest": eps_non_gaap_8k,
            "comps": extract_comps(text_8k) if text_8k else {},
            "margin_line": extract_margin_line(text_8k) if text_8k else None,
            "guidance_text": extract_guidance_text(blocks_8k) if blocks_8k else None,
        },
        "xbrl_company_facts": {
            "revenue_annual": xbrl.get("revenue_annual"),
            "revenue_yoy": xbrl.get("revenue_yoy"),
            "eps_annual_gaap": xbrl.get("eps_annual_gaap"),
            "shares_outstanding": xbrl.get("shares_outstanding"),
            "dividend_annual": xbrl.get("dividend_annual"),
            "cash": xbrl.get("cash"),
            "total_debt": xbrl.get("total_debt"),
            "net_debt": xbrl.get("net_debt"),
            "business_fact": business_fact,
        },
    }
    if show_headings:
        out["debug_short_blocks_8k"] = [b for b in blocks_8k if len(b) <= 100][:30]
    return out


if __name__ == "__main__":
    target_ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    show_h = "--show-headings" in sys.argv
    print(json.dumps(fetch_edgar_summary(target_ticker, show_headings=show_h), indent=2))
