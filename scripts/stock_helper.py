import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------
ENDPOINTS: Dict[str, str] = {
    "overview": "",
    "forecast": "/stock-forecast",
    "revenue": "/revenue",
    "ownership": "/ownership",
    "financials": "/financials",
}

# The site stores series newest-first and the longest series is ~63 entries.
# 100 keeps every real series whole while bounding pathological payloads.
MAX_SERIES_ENTRIES = 100

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html",
}

TIMEOUT_SECONDS = 15.0

# ---------------------------------------------------------------------------
# Sanitization Logic
# ---------------------------------------------------------------------------
def sanitize_for_llm(data: Any) -> Any:
    """
    Strips raw HTML, null blobs, and deep component tree metadata
    to keep tokens concise for LLMs (e.g. Ollama).
    """
    if data is None:
        return None

    if isinstance(data, list):
        # Dated time-series: if every element is an object with a 'date' string
        is_dated_series = (
            len(data) > MAX_SERIES_ENTRIES
            and all(isinstance(item, dict) and isinstance(item.get("date"), str) for item in data)
        )

        if is_dated_series:
            # Sort newest-first (descending) and cap at MAX_SERIES_ENTRIES
            sorted_items = sorted(
                data,
                key=lambda item: str(item.get("date", "")),
                reverse=True,
            )
            return [sanitize_for_llm(x) for x in sorted_items[:MAX_SERIES_ENTRIES]]

        return [sanitize_for_llm(x) for x in data]

    if isinstance(data, dict):
        cleaned: Dict[str, Any] = {}
        for key, value in data.items():
            # Exclude Next.js internal props and noisy state blobs
            if key.startswith("__") or key in {"page", "dehydratedState", "apolloState"}:
                continue

            sanitized = sanitize_for_llm(value)
            if sanitized is not None:
                cleaned[key] = sanitized
        return cleaned

    return data


# ---------------------------------------------------------------------------
# Scraper Logic
# ---------------------------------------------------------------------------
async def fetch_section(
    client: httpx.AsyncClient, ticker: str, section: str, path: str
) -> tuple[str, Any]:
    target_url = f"https://www.tickergate.com/stocks/{ticker}{path}"
    try:
        res = await client.get(target_url, headers=DEFAULT_HEADERS, timeout=TIMEOUT_SECONDS)
        if res.status_code != 200:
            return section, {"error": f"HTTP status {res.status_code}"}

        # Extract __NEXT_DATA__ JSON script tag
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            res.text,
            re.DOTALL,
        )

        if match and match.group(1):
            parsed = json.loads(match.group(1))
            page_props = parsed.get("props", {}).get("pageProps", {})
            return section, sanitize_for_llm(page_props)

        return section, {"error": "No structured data found on page"}
    except Exception as err:
        return section, {"error": str(err)}


async def get_stock_data(ticker: str, requested_sections: List[str]) -> Dict[str, Any]:
    ticker = ticker.strip().lower()

    if "all" in requested_sections:
        target_entries = list(ENDPOINTS.items())
    else:
        target_entries = [
            (sec, path) for sec, path in ENDPOINTS.items() if sec in requested_sections
        ]

    # Concurrent fetch using HTTPX AsyncClient
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [
            fetch_section(client, ticker, sec, path)
            for sec, path in target_entries
        ]
        results = await asyncio.gather(*tasks)

    return {
        "symbol": ticker.upper(),
        "source": "tickergate",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sections": dict(results),
    }


# ---------------------------------------------------------------------------
# FastAPI Web Service
# ---------------------------------------------------------------------------
app = FastAPI(title="Stock Data Helper")

# Enable CORS for cross-origin frontend calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StockRequest(BaseModel):
    ticker: Optional[str] = "AAPL"
    sections: Optional[List[str]] = ["overview", "forecast"]


@app.get("/")
async def root_get(
    ticker: str = Query("AAPL"),
    sections: Optional[str] = Query(None),
):
    section_list = ["overview", "forecast"]
    if sections:
        section_list = [s.strip().lower() for s in sections.split(",") if s.strip()]
    return await get_stock_data(ticker=ticker, requested_sections=section_list)


@app.post("/")
async def root_post(req: StockRequest):
    ticker = req.ticker or "AAPL"
    sections = [s.lower() for s in req.sections] if req.sections else ["overview", "forecast"]
    return await get_stock_data(ticker=ticker, requested_sections=sections)


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # If run with --serve, start the web server
    if "--serve" in sys.argv:
        import uvicorn
        port = 8000
        for arg in sys.argv:
            if arg.startswith("--port="):
                port = int(arg.split("=")[1])
        print(f"Starting server on http://0.0.0.0:{port}")
        uvicorn.run("stock_helper:app", host="0.0.0.0", port=port, reload=False)
    else:
        # CLI test run: python stock_helper.py <ticker> <sections_comma_separated>
        cli_ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
        cli_sections = (
            sys.argv[2].split(",") if len(sys.argv) > 2 else ["overview", "forecast"]
        )
        print(f"Fetching data for {cli_ticker} with sections: {cli_sections}...")
        data = asyncio.run(get_stock_data(cli_ticker, cli_sections))
        print(json.dumps(data, indent=2))