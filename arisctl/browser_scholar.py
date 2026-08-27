"""Bounded, visible-browser Google Scholar retrieval for the research-lit gateway.

This adapter intentionally models a single manual researcher action: it opens a
fresh, visible Chrome session, visits one Scholar results page, reads the visible
result cards, and closes the temporary profile.  It has no login support, never
solves challenges, never rotates proxies, and does not retry a blocked page.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen


class BrowserScholarError(RuntimeError):
    """A direct Scholar browser session could not safely provide a result page."""

    def __init__(self, message: str, *, blocked: bool = False):
        super().__init__(message)
        self.blocked = blocked


_CHROME_CANDIDATES = (
    Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
)
_BLOCK_MARKERS = ("unusual traffic", "not a robot", "recaptcha", "we're sorry")
_SEARCH_LOCK = threading.Lock()
_LAST_SEARCH_FINISHED = 0.0
_MIN_SECONDS_BETWEEN_SEARCHES = 10.0
_EXTRACT_SCRIPT = """
(() => JSON.stringify({
  page_text: document.body.innerText.slice(0, 2500),
  results: Array.from(document.querySelectorAll('#gs_res_ccl_mid .gs_ri')).map(card => {
    const anchor = card.querySelector('h3.gs_rt a');
    const cited = Array.from(card.querySelectorAll('a')).find(
      link => /^Cited by\\s+\\d+$/i.test(link.innerText.trim())
    );
    return {
      title: card.querySelector('h3.gs_rt')?.innerText?.trim() || '',
      link: anchor?.href || null,
      year_venue_raw: card.querySelector('.gs_a')?.innerText?.trim() || null,
      citation_count: cited ? Number((cited.innerText.match(/\\d+/) || [''])[0]) : null,
      cited_by_url: cited?.href || null,
      snippet: card.querySelector('.gs_rs')?.innerText?.trim() || null
    };
  })
}))()
"""


def parse_year_venue(raw: str | None) -> tuple[int | None, str | None]:
    """Conservatively parse Scholar's visible ``authors - venue, year - host`` line."""

    if not raw:
        return None, None
    normalized = raw.replace("\u00a0", " ")
    pieces = [piece.strip() for piece in re.split(r"\s+-\s+", normalized)]
    bibliographic = pieces[1] if len(pieces) >= 2 else normalized.strip()
    years = re.findall(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", bibliographic)
    year = int(years[-1]) if years else None
    venue = re.sub(r",?\s*(?:18|19|20)\d{2}\b", "", bibliographic).strip(" ,")
    return year, venue or None


def normalize_scholar_result(item: dict[str, Any]) -> dict[str, Any]:
    """Map one visible Scholar card to the gateway's discovery-result schema."""

    cited_by_url = str(item.get("cited_by_url") or "") or None
    cited_by_id = None
    if cited_by_url:
        cited_by_id = (parse_qs(urlsplit(cited_by_url).query).get("cites") or [None])[0]
    year, venue = parse_year_venue(str(item.get("year_venue_raw") or "") or None)
    title = str(item.get("title") or "")
    link = str(item.get("link") or "") or None
    paper_id = f"scholar:{cited_by_id}" if cited_by_id else (link or title)
    return {
        "paper_id": paper_id,
        "title": title,
        "year": year,
        "venue": venue,
        "doi_or_stable_url": link,
        "citation_count": item.get("citation_count"),
        "citation_source": "google_scholar",
        "cited_by_id": cited_by_id,
        "cited_by_url": cited_by_url,
        "snippet": item.get("snippet"),
        "identity_status": "verify_pending",
        "discovery_provider": "scholar_google_hk",
    }


def _find_chrome() -> Path:
    for candidate in _CHROME_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise BrowserScholarError("Google Chrome is not installed")


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_debugger(port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1):  # noqa: S310 -- local Chrome DevTools only
                return
        except OSError:
            time.sleep(0.25)
    raise BrowserScholarError("visible Chrome did not expose its local debugging endpoint")


class _CDP:
    def __init__(self, websocket_url: str):
        parts = urlsplit(websocket_url)
        self.socket = socket.create_connection((parts.hostname, parts.port), timeout=15)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        handshake = (
            f"GET {parts.path} HTTP/1.1\r\nHost: {parts.hostname}:{parts.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.socket.sendall(handshake)
        response = self._read_headers()
        if not response.splitlines() or b" 101 " not in response.splitlines()[0]:
            raise BrowserScholarError("could not attach to the visible Chrome tab")
        self.request_id = 0

    def _read_headers(self) -> bytes:
        received = bytearray()
        while b"\r\n\r\n" not in received:
            chunk = self.socket.recv(4096)
            if not chunk:
                raise BrowserScholarError("Chrome closed while the browser tab was opening")
            received.extend(chunk)
        return bytes(received)

    def _recv_exact(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = self.socket.recv(size - len(data))
            if not chunk:
                raise BrowserScholarError("Chrome closed during Scholar retrieval")
            data.extend(chunk)
        return bytes(data)

    def _send(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        size = len(body)
        if size < 126:
            header = bytes((0x81, 0x80 | size))
        elif size <= 0xFFFF:
            header = bytes((0x81, 0x80 | 126)) + struct.pack("!H", size)
        else:
            header = bytes((0x81, 0x80 | 127)) + struct.pack("!Q", size)
        mask = secrets.token_bytes(4)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(body))
        self.socket.sendall(header + mask + masked)

    def _recv(self) -> tuple[int, bytes]:
        first, second = self._recv_exact(2)
        size = second & 0x7F
        if size == 126:
            size = struct.unpack("!H", self._recv_exact(2))[0]
        elif size == 127:
            size = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if second & 0x80 else b""
        payload = self._recv_exact(size)
        if mask:
            payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        return first & 0x0F, payload

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.request_id += 1
        request_id = self.request_id
        self._send({"id": request_id, "method": method, "params": params or {}})
        while True:
            opcode, payload = self._recv()
            if opcode == 0x9:  # ping
                self.socket.sendall(bytes((0x8A, len(payload))) + payload)
                continue
            if opcode == 0x8:
                raise BrowserScholarError("Chrome closed during Scholar retrieval")
            if opcode != 0x1:
                continue
            message = json.loads(payload)
            if message.get("id") == request_id:
                if "error" in message:
                    raise BrowserScholarError(f"Chrome DevTools rejected {method}")
                return message["result"]

    def close(self) -> None:
        self.socket.close()


def _scholar_url(
    query: str,
    page: int,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    exact_title: bool = False,
    cited_by: str | None = None,
) -> str:
    # Scholar's default ten-result view matches normal interactive navigation.
    start = max(0, page - 1) * 10
    params: dict[str, str | int] = {
        "hl": "en",
        "as_sdt": "0,5",
        "q": f'"{query}"' if exact_title else query,
        "start": start,
    }
    if year_from is not None:
        params["as_ylo"] = year_from
    if year_to is not None:
        params["as_yhi"] = year_to
    if cited_by:
        params["cites"] = cited_by
    return "https://scholar.google.hk/scholar?" + urlencode(params)


def _read_visible_page(cdp: _CDP, url: str) -> list[dict[str, Any]]:
    cdp.call("Page.navigate", {"url": url})
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        time.sleep(0.75)
        result = cdp.call("Runtime.evaluate", {"expression": _EXTRACT_SCRIPT, "returnByValue": True})
        raw = result.get("result", {}).get("value")
        if not isinstance(raw, str):
            continue
        page = json.loads(raw)
        visible_text = str(page.get("page_text") or "").casefold()
        if any(marker in visible_text for marker in _BLOCK_MARKERS):
            raise BrowserScholarError("Scholar displayed a block or CAPTCHA page", blocked=True)
        cards = page.get("results") or []
        if cards:
            return [normalize_scholar_result(card) for card in cards if isinstance(card, dict)]
        if "no results" in visible_text:
            return []
    raise BrowserScholarError("Scholar results did not render within the bounded wait period")


def _search_google_scholar_once(
    query: str,
    *,
    page: int = 1,
    year_from: int | None = None,
    year_to: int | None = None,
    exact_title: bool = False,
    cited_by: str | None = None,
) -> list[dict[str, Any]]:
    """Read exactly one normal Scholar result page from a visible temporary browser."""

    if page < 1:
        raise BrowserScholarError("Scholar page must be at least 1")
    port = _free_local_port()
    profile = Path(tempfile.mkdtemp(prefix="aris-scholar-browser-"))
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
        return _read_visible_page(
            cdp,
            _scholar_url(
                query,
                page,
                year_from=year_from,
                year_to=year_to,
                exact_title=exact_title,
                cited_by=cited_by,
            ),
        )
    except BrowserScholarError:
        raise
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise BrowserScholarError(f"visible browser retrieval failed: {exc}") from exc
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


def search_google_scholar(
    query: str,
    *,
    page: int = 1,
    year_from: int | None = None,
    year_to: int | None = None,
    exact_title: bool = False,
    cited_by: str | None = None,
) -> list[dict[str, Any]]:
    """Read one Scholar page, serializing sessions with a conservative cooldown."""

    global _LAST_SEARCH_FINISHED
    with _SEARCH_LOCK:
        wait_seconds = _MIN_SECONDS_BETWEEN_SEARCHES - (time.monotonic() - _LAST_SEARCH_FINISHED)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        try:
            return _search_google_scholar_once(
                query,
                page=page,
                year_from=year_from,
                year_to=year_to,
                exact_title=exact_title,
                cited_by=cited_by,
            )
        finally:
            _LAST_SEARCH_FINISHED = time.monotonic()
