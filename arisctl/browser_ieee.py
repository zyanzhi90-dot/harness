"""Bounded, visible-browser IEEE Xplore retrieval for the research-lit gateway.

This is deliberately a single normal search action rather than a scraper: a
fresh visible Chrome profile opens one public IEEE Xplore results page, reads
the visible result cards, and closes.  It has no login, cookie reuse, automatic
pagination, challenge handling, proxy rotation, or retry behaviour.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from .browser_scholar import (
    BrowserScholarError,
    _CDP,
    _find_chrome,
    _free_local_port,
    _wait_for_debugger,
)


class BrowserIeeeError(RuntimeError):
    """A direct IEEE Xplore browser session could not safely provide results."""

    def __init__(self, message: str, *, blocked: bool = False):
        super().__init__(message)
        self.blocked = blocked


_BLOCK_MARKERS = ("unusual traffic", "not a robot", "recaptcha", "access denied")
_SEARCH_LOCK = threading.Lock()
_LAST_SEARCH_FINISHED = 0.0
_MIN_SECONDS_BETWEEN_SEARCHES = 15.0
_EXTRACT_SCRIPT = r"""
(() => JSON.stringify({
  page_text: document.body.innerText.slice(0, 3000),
  results: (() => {
    const seen = new Set();
    return Array.from(document.querySelectorAll('a[href*="/document/"]'))
      .filter(anchor => anchor.href && anchor.innerText.trim())
      .filter(anchor => !/^Papers\s*\(\d+\)$/i.test(anchor.innerText.trim()))
      .filter(anchor => {
        if (seen.has(anchor.href)) return false;
        seen.add(anchor.href);
        return true;
      })
      .slice(0, 10)
      .map(anchor => {
        const card = anchor.closest('xpl-search-result-item, xpl-search-result, .List-results-item, .result-item, article, li')
          || anchor.parentElement;
        const text = card?.innerText?.trim() || anchor.parentElement?.innerText?.trim() || '';
        const cited = text.match(/Cited\s+by\s*:?(?:\s+Papers)?\s*\(?(\d+)\)?/i);
        return {
          title: anchor.innerText.trim(),
          link: anchor.href,
          metadata_raw: text,
          citation_count: cited ? Number(cited[1]) : null,
          snippet: text || null
        };
      });
  })()
}))()
"""


def _ieee_url(query: str, page: int, *, exact_title: bool = False) -> str:
    page_number = max(1, page)
    effective_query = f'"{query}"' if exact_title else query
    return (
        "https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText="
        + quote_plus(effective_query)
        + f"&pageNumber={page_number}"
    )


def parse_year_venue(raw: str | None) -> tuple[int | None, str | None]:
    """Extract only a visible year and IEEE publication label from a result card."""

    normalized = (raw or "").replace("\u00a0", " ")
    years = re.findall(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", normalized)
    year = int(years[0]) if years else None
    lines = [line.strip(" -,:;") for line in normalized.splitlines() if line.strip()]
    year_line_index = next((index for index, line in enumerate(lines) if "year:" in line.casefold()), None)
    venue = lines[year_line_index - 1] if year_line_index and year_line_index > 0 else None
    if not venue:
        venue = next(
            (
                line
                for line in lines
                if line.casefold().startswith("ieee ")
                and "ieee xplore" not in line.casefold()
                and len(line) > 6
            ),
            None,
        )
    return year, venue or None


def normalize_ieee_result(item: dict[str, Any]) -> dict[str, Any]:
    """Map one visible IEEE result card to the discovery-result schema."""

    link = str(item.get("link") or "") or None
    document = re.search(r"/document/(\d+)", link or "")
    year, venue = parse_year_venue(str(item.get("metadata_raw") or "") or None)
    title = str(item.get("title") or "")
    return {
        "paper_id": f"ieee:{document.group(1)}" if document else (link or title),
        "title": title,
        "year": year,
        "venue": venue,
        "doi": None,
        "doi_or_stable_url": link,
        "citation_count": item.get("citation_count"),
        "citation_source": "ieee_xplore_visible" if item.get("citation_count") is not None else None,
        "snippet": item.get("snippet"),
        "identity_status": "verify_pending",
        "discovery_provider": "ieee_xplore",
        "retrieval_method": "visible_browser",
    }


def _read_visible_page(cdp: _CDP, url: str) -> list[dict[str, Any]]:
    cdp.call("Page.navigate", {"url": url})
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        time.sleep(0.75)
        result = cdp.call("Runtime.evaluate", {"expression": _EXTRACT_SCRIPT, "returnByValue": True})
        raw = result.get("result", {}).get("value")
        if not isinstance(raw, str):
            continue
        page = json.loads(raw)
        visible_text = str(page.get("page_text") or "").casefold()
        if any(marker in visible_text for marker in _BLOCK_MARKERS):
            raise BrowserIeeeError("IEEE Xplore displayed a block or CAPTCHA page", blocked=True)
        cards = page.get("results") or []
        if cards:
            return [normalize_ieee_result(card) for card in cards if isinstance(card, dict)]
        if "no results" in visible_text or "0 results" in visible_text:
            return []
    raise BrowserIeeeError("IEEE Xplore results did not render within the bounded wait period")


def _search_ieee_once(
    query: str, *, page: int = 1, exact_title: bool = False
) -> list[dict[str, Any]]:
    """Read exactly one public IEEE Xplore result page from visible Chrome."""

    if page < 1:
        raise BrowserIeeeError("IEEE Xplore page must be at least 1")
    port = _free_local_port()
    profile = Path(tempfile.mkdtemp(prefix="aris-ieee-browser-"))
    process: subprocess.Popen[bytes] | None = None
    cdp: _CDP | None = None
    try:
        process = subprocess.Popen([
            str(_find_chrome()), f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check", "about:blank",
        ])
        _wait_for_debugger(port)
        request = Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
        with urlopen(request, timeout=5) as response:  # noqa: S310 -- local Chrome DevTools only
            target = json.load(response)
        cdp = _CDP(str(target["webSocketDebuggerUrl"]))
        cdp.call("Page.enable")
        return _read_visible_page(cdp, _ieee_url(query, page, exact_title=exact_title))
    except BrowserIeeeError:
        raise
    except BrowserScholarError as exc:
        raise BrowserIeeeError(str(exc), blocked=exc.blocked) from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise BrowserIeeeError(f"visible browser retrieval failed: {exc}") from exc
    finally:
        if cdp is not None:
            cdp.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        shutil.rmtree(profile, ignore_errors=True)


def search_ieee_xplore(
    query: str, *, page: int = 1, exact_title: bool = False
) -> list[dict[str, Any]]:
    """Read one IEEE page, serializing sessions with a conservative cooldown."""

    global _LAST_SEARCH_FINISHED
    with _SEARCH_LOCK:
        wait_seconds = _MIN_SECONDS_BETWEEN_SEARCHES - (time.monotonic() - _LAST_SEARCH_FINISHED)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        try:
            return _search_ieee_once(query, page=page, exact_title=exact_title)
        finally:
            _LAST_SEARCH_FINISHED = time.monotonic()
