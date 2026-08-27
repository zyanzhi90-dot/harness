"""Controlled research and paper-access gateways with immutable event ledgers."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .browser_scholar import BrowserScholarError, search_google_scholar as browser_scholar_search
from .browser_ieee import BrowserIeeeError, search_ieee_xplore as browser_ieee_search


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    previous_hash: str | None = None
    if target.is_file():
        lines = [line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
        if lines:
            previous = json.loads(lines[-1])
            previous_hash = previous.get("record_sha256")
    chained = dict(row)
    # Hash-chain fields belong to this append boundary.  A row restored from
    # an earlier canonical snapshot must not smuggle its old receipt into the
    # semantic payload of a new record.
    chained.pop("previous_record_sha256", None)
    chained.pop("record_sha256", None)
    chained["previous_record_sha256"] = previous_hash
    canonical = json.dumps(chained, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    chained["record_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(chained, ensure_ascii=False, sort_keys=True) + "\n")


def repair_embedded_record_hash_contamination(path: str | Path) -> dict[str, Any]:
    """Repair only the legacy writer defect that hashed an embedded old receipt.

    Every invalid row must be reproducible by inserting a prior hash from the
    same source into ``record_sha256`` before hashing.  Any other corruption,
    broken link, or malformed row fails closed.
    """

    target = Path(path)
    lines = [line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [json.loads(line) for line in lines]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("registry repair requires JSON-object rows")

    previous: str | None = None
    known_by_source: dict[str, list[str]] = {}
    contaminated_rows: list[int] = []
    for index, row in enumerate(rows, 1):
        if row.get("previous_record_sha256") != previous:
            raise ValueError("registry repair refused a broken append-only link")
        recorded = row.get("record_sha256")
        if not isinstance(recorded, str):
            raise ValueError("registry repair requires an existing record hash")
        unhashed = dict(row)
        unhashed.pop("record_sha256", None)
        canonical = json.dumps(
            unhashed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        calculated = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        source_id = str(row.get("source_id") or row.get("paper_id") or "")
        if recorded != calculated:
            matched_legacy_signature = False
            for old_hash in known_by_source.get(source_id, []):
                contaminated = dict(row)
                contaminated["record_sha256"] = old_hash
                legacy_canonical = json.dumps(
                    contaminated,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if hashlib.sha256(legacy_canonical.encode("utf-8")).hexdigest() == recorded:
                    matched_legacy_signature = True
                    break
            if not matched_legacy_signature:
                raise ValueError(
                    f"registry repair refused unrecognized hash corruption at row {index}"
                )
            contaminated_rows.append(index)
        known_by_source.setdefault(source_id, []).append(recorded)
        previous = recorded

    if not contaminated_rows:
        raise ValueError("registry has no recognized embedded-record-hash contamination")

    repaired_rows: list[dict[str, Any]] = []
    previous = None
    for row in rows:
        repaired = dict(row)
        repaired.pop("previous_record_sha256", None)
        repaired.pop("record_sha256", None)
        repaired["previous_record_sha256"] = previous
        canonical = json.dumps(
            repaired, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        repaired["record_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        repaired_rows.append(repaired)
        previous = repaired["record_sha256"]

    temporary = target.with_name(f".{target.name}.repair-{os.getpid()}")
    try:
        temporary.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in repaired_rows
            ),
            encoding="utf-8",
        )
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "row_count": len(repaired_rows),
        "contaminated_rows": contaminated_rows,
        "first_repaired_row": min(contaminated_rows),
    }


def ledger_event(
    *,
    run_id: str,
    stage: str,
    action: str,
    tool: str,
    result_status: str,
    event_id: str,
    query_id: str | None = None,
    query: str | None = None,
    paper_id: str | None = None,
    admission_decision: str | None = None,
    budget_before: dict[str, int] | None = None,
    budget_after: dict[str, int] | None = None,
    artifact_sha256: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "timestamp": now(),
        "run_id": run_id,
        "stage": stage,
        "action": action,
        "query_id": query_id,
        "query": query,
        "paper_id": paper_id,
        "tool": tool,
        "result_status": result_status,
        "admission_decision": admission_decision,
        "budget_before": budget_before,
        "budget_after": budget_after,
        "artifact_sha256": artifact_sha256,
        "details": details,
    }


@dataclass(frozen=True)
class ScholarQueryOptions:
    """Google Scholar capabilities used by the research-lit query gateway."""

    year_from: int | None = None
    year_to: int | None = None
    exact_title: bool = False
    page: int = 1
    cited_by: str | None = None
    page_size: int = 20


@dataclass
class SearchOutcome:
    results: list[dict[str, Any]]
    provider: str
    google_scholar_coverage: bool
    attempts: list[dict[str, str]] = field(default_factory=list)
    query_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FullTextPayload:
    """Bytes and source provenance returned by a controlled full-text gateway."""

    content: bytes
    source_url: str
    media_type: str
    provider: str


class ProviderUnavailable(RuntimeError):
    def __init__(self, provider: str, reason: str, *, blocked: bool = False):
        super().__init__(f"{provider} unavailable: {reason}")
        self.provider = provider
        self.reason = reason
        self.blocked = blocked

    def attempt(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "status": "blocked" if self.blocked else "unavailable",
            "reason": self.reason,
        }


class HumanSearchRequired(RuntimeError):
    def __init__(
        self,
        attempts: list[dict[str, str]],
        *,
        query_options: dict[str, Any] | None = None,
    ):
        super().__init__("HUMAN_SEARCH_REQUIRED")
        self.attempts = attempts
        self.query_options = dict(query_options or {})


JsonFetcher = Callable[[str, float, dict[str, str]], dict[str, Any]]
TextFetcher = Callable[[str, float, dict[str, str]], str]
SearchCallable = Callable[[str], list[dict[str, Any]] | SearchOutcome]
ReadCallable = Callable[[dict[str, Any]], Any]
MetadataVerifyCallable = Callable[[dict[str, Any]], dict[str, Any]]


def _doi_from_paper(paper: dict[str, Any]) -> str:
    doi = str(paper.get("doi") or "").strip()
    if doi:
        return doi
    stable = str(paper.get("doi_or_stable_url") or "")
    match = re.search(r"(?:doi\.org/|doi:)(10\.\d{4,9}/\S+)", stable, re.I)
    return match.group(1).rstrip(".,)") if match else ""


def semantic_scholar_open_access_fulltext(
    paper: dict[str, Any],
    *,
    fetch_json: JsonFetcher | None = None,
    fetch_bytes: Callable[[str, float, dict[str, str]], bytes] | None = None,
    timeout: float = 30.0,
) -> FullTextPayload:
    """Resolve an admitted DOI to a real open-access PDF without using search quota."""

    provider = "semantic_scholar_open_access"
    doi = _doi_from_paper(paper)
    if not doi:
        raise ProviderUnavailable(provider, "admitted paper has no DOI")
    paper_ref = urllib.parse.quote(f"DOI:{doi}", safe=":")
    fields = urllib.parse.urlencode(
        {"fields": "title,externalIds,openAccessPdf"}
    )
    metadata_url = (
        "https://api.semanticscholar.org/graph/v1/paper/"
        f"{paper_ref}?{fields}"
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": "ARIS-research-lit/2.0",
    }
    if fetch_json is None:
        fetch_json = _fetch_json
    try:
        metadata = fetch_json(metadata_url, timeout, headers)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise _provider_network_error(provider, exc) from exc
    returned_doi = str((metadata.get("externalIds") or {}).get("DOI") or "")
    if returned_doi.casefold() != doi.casefold():
        raise ProviderUnavailable(provider, "resolver DOI did not match admitted DOI")
    pdf_url = str((metadata.get("openAccessPdf") or {}).get("url") or "").strip()
    if not pdf_url.startswith("https://"):
        raise ProviderUnavailable(provider, "no HTTPS open-access PDF is available")

    if fetch_bytes is None:
        def fetch_bytes(url: str, request_timeout: float, request_headers: dict[str, str]) -> bytes:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=request_timeout) as response:  # noqa: S310
                return response.read()

    try:
        content = fetch_bytes(
            pdf_url,
            timeout,
            {"Accept": "application/pdf", "User-Agent": "ARIS-research-lit/2.0"},
        )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise _provider_network_error(provider, exc) from exc
    if not content.startswith(b"%PDF-"):
        raise ProviderUnavailable(provider, "resolved object is not a PDF")
    return FullTextPayload(
        content=content,
        source_url=pdf_url,
        media_type="application/pdf",
        provider=provider,
    )


def crossref_declared_fulltext(
    paper: dict[str, Any],
    *,
    fetch_json: JsonFetcher | None = None,
    fetch_bytes: Callable[[str, float, dict[str, str]], bytes] | None = None,
    timeout: float = 30.0,
) -> FullTextPayload:
    """Fetch a DOI publisher full-text object explicitly declared by Crossref."""

    provider = "crossref_declared_fulltext"
    doi = _doi_from_paper(paper)
    if not doi:
        raise ProviderUnavailable(provider, "admitted paper has no DOI")
    if fetch_json is None:
        fetch_json = _fetch_json
    if fetch_bytes is None:
        def fetch_bytes(url: str, request_timeout: float, request_headers: dict[str, str]) -> bytes:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=request_timeout) as response:  # noqa: S310
                return response.read()

    metadata_url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    try:
        metadata = fetch_json(
            metadata_url,
            timeout,
            {"Accept": "application/json", "User-Agent": "ARIS-research-lit/2.0"},
        )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise _provider_network_error(provider, exc) from exc
    links = (metadata.get("message") or {}).get("link") or []
    supported = {"application/pdf": 0, "application/xml": 1, "text/xml": 1}
    candidates = sorted(
        (
            link for link in links
            if isinstance(link, dict)
            and str(link.get("content-type") or "").casefold() in supported
            and str(link.get("URL") or "").startswith(("https://", "http://"))
        ),
        key=lambda link: supported[str(link.get("content-type")).casefold()],
    )
    if not candidates:
        raise ProviderUnavailable(provider, "Crossref declares no supported full-text object")
    last_error: ProviderUnavailable | None = None
    for link in candidates:
        media_type = str(link.get("content-type")).casefold()
        source_url = str(link.get("URL"))
        try:
            content = fetch_bytes(
                source_url,
                timeout,
                {"Accept": media_type, "User-Agent": "ARIS-research-lit/2.0"},
            )
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = _provider_network_error(provider, exc)
            continue
        if media_type == "application/pdf" and not content.startswith(b"%PDF-"):
            last_error = ProviderUnavailable(provider, "declared PDF response is not a PDF")
            continue
        if media_type in {"application/xml", "text/xml"} and not content.lstrip().startswith(b"<"):
            last_error = ProviderUnavailable(provider, "declared XML response is not XML")
            continue
        return FullTextPayload(content, source_url, media_type, provider)
    raise last_error or ProviderUnavailable(provider, "declared full-text objects were unavailable")


def openalex_open_access_fulltext(
    paper: dict[str, Any],
    *,
    fetch_json: JsonFetcher | None = None,
    fetch_bytes: Callable[[str, float, dict[str, str]], bytes] | None = None,
    timeout: float = 30.0,
) -> FullTextPayload:
    """Resolve a DOI through OpenAlex and fetch its declared OA PDF."""

    provider = "openalex_open_access"
    doi = _doi_from_paper(paper)
    if not doi:
        raise ProviderUnavailable(provider, "admitted paper has no DOI")
    if fetch_json is None:
        fetch_json = _fetch_json
    if fetch_bytes is None:
        def fetch_bytes(url: str, request_timeout: float, request_headers: dict[str, str]) -> bytes:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=request_timeout) as response:  # noqa: S310
                return response.read()

    metadata_url = (
        "https://api.openalex.org/works/doi:"
        + urllib.parse.quote(doi, safe="")
    )
    headers = {"Accept": "application/json", "User-Agent": "ARIS-research-lit/2.0"}
    try:
        metadata = fetch_json(metadata_url, timeout, headers)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise _provider_network_error(provider, exc) from exc
    returned_doi = str(metadata.get("doi") or "").removeprefix("https://doi.org/")
    if returned_doi.casefold() != doi.casefold():
        raise ProviderUnavailable(provider, "resolver DOI did not match admitted DOI")
    location = metadata.get("best_oa_location") or {}
    pdf_url = str(location.get("pdf_url") or "").strip()
    if not pdf_url.startswith(("https://", "http://")):
        raise ProviderUnavailable(provider, "no open-access PDF is declared")
    try:
        content = fetch_bytes(
            pdf_url,
            timeout,
            {"Accept": "application/pdf", "User-Agent": "ARIS-research-lit/2.0"},
        )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise _provider_network_error(provider, exc) from exc
    if not content.startswith(b"%PDF-"):
        raise ProviderUnavailable(provider, "declared PDF response is not a PDF")
    return FullTextPayload(content, pdf_url, "application/pdf", provider)


def open_access_fulltext(paper: dict[str, Any]) -> FullTextPayload:
    """Fetch only an admitted paper whose identity declares an arXiv URL."""

    return arxiv_declared_fulltext(paper)


def arxiv_declared_fulltext(
    paper: dict[str, Any],
    *,
    timeout: float = 30.0,
    fetch_bytes: Callable[[str, float, dict[str, str]], bytes] | None = None,
) -> FullTextPayload:
    """Fetch a PDF only when the admitted identity declares an arXiv ID or URL."""

    provider = "arxiv_declared_fulltext"
    arxiv_id = str(paper.get("arxiv_id") or "").strip().removesuffix(".pdf")
    stable = str(paper.get("doi_or_stable_url") or "").strip()
    if not arxiv_id and "arxiv.org/" not in stable.casefold():
        raise ProviderUnavailable(provider, "admitted paper has no arXiv identity")
    if not arxiv_id:
        match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#]+)", stable, re.I)
        if not match:
            raise ProviderUnavailable(provider, "invalid arXiv identity URL")
        arxiv_id = match.group(1).removesuffix(".pdf")
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    getter = fetch_bytes
    try:
        if getter is None:
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/pdf", "User-Agent": "ARIS-research-lit/2.0"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                content = response.read()
        else:
            content = getter(
                url,
                timeout,
                {"Accept": "application/pdf", "User-Agent": "ARIS-research-lit/2.0"},
            )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise _provider_network_error(provider, exc) from exc
    if not content.startswith(b"%PDF-"):
        raise ProviderUnavailable(provider, "arXiv response is not a PDF")
    return FullTextPayload(content, url, "application/pdf", provider)


def _fetch_json(url: str, timeout: float, headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("provider response must be a JSON object")
    return payload


def _fetch_text(url: str, timeout: float, headers: dict[str, str]) -> str:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def _provider_network_error(provider: str, exc: BaseException) -> ProviderUnavailable:
    if isinstance(exc, urllib.error.HTTPError):
        blocked = exc.code in {403, 429}
        return ProviderUnavailable(provider, f"HTTP {exc.code}", blocked=blocked)
    if isinstance(exc, TimeoutError):
        return ProviderUnavailable(provider, "timeout")
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            return ProviderUnavailable(provider, "timeout")
        return ProviderUnavailable(provider, "network error")
    return ProviderUnavailable(provider, "service response error")


def _year_from_text(text: str) -> int | None:
    match = re.search(r"\b(?:19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()


def _crossref_identity_score(paper: dict[str, Any], item: dict[str, Any]) -> tuple[int, int, int, int]:
    """Disambiguate exact-title Crossref records using discovery metadata."""

    expected_doi = str(paper.get("doi") or "").strip().casefold()
    candidate_doi = str(item.get("DOI") or "").strip().casefold()
    doi_score = int(bool(expected_doi) and candidate_doi == expected_doi)

    date = item.get("published-print") or item.get("published-online") or item.get("issued") or {}
    parts = date.get("date-parts") or []
    candidate_year = parts[0][0] if parts and parts[0] else None
    expected_year = paper.get("year")
    year_score = 0
    if isinstance(expected_year, int) and isinstance(candidate_year, int):
        year_score = 2 if candidate_year == expected_year else int(abs(candidate_year - expected_year) <= 1)

    expected_venue = set(_normalize_title(str(paper.get("venue") or "")).split())
    candidate_venue = set(
        _normalize_title(str((item.get("container-title") or [""])[0])).split()
    )
    venue_score = len(expected_venue & candidate_venue)

    expected_families = {
        _normalize_title(str(author)).split()[-1]
        for author in paper.get("authors") or []
        if _normalize_title(str(author))
    }
    candidate_families = {
        _normalize_title(str(author.get("family") or ""))
        for author in item.get("author") or []
        if isinstance(author, dict) and _normalize_title(str(author.get("family") or ""))
    }
    author_score = len(expected_families & candidate_families)
    return doi_score, venue_score, year_score, author_score


def crossref_verify_metadata(
    paper: dict[str, Any],
    *,
    fetch_json: JsonFetcher = _fetch_json,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Verify one discovered identity against Crossref without another Scholar query."""

    provider = "crossref_metadata"
    title = str(paper.get("title") or "").strip()
    if not title:
        raise ValueError("metadata verification requires a title")
    params = urllib.parse.urlencode(
        {
            "query.title": title,
            "rows": 5,
            "select": "DOI,title,author,published-print,published-online,issued,container-title,URL,type,abstract",
        }
    )
    url = f"https://api.crossref.org/works?{params}"
    try:
        payload = fetch_json(
            url,
            timeout,
            {"Accept": "application/json", "User-Agent": "ARIS-research-lit/2.0"},
        )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise _provider_network_error(provider, exc) from exc
    items = ((payload.get("message") or {}).get("items") or [])
    expected = _normalize_title(title)
    exact_matches = [
        item
        for item in items
        if isinstance(item, dict)
        and _normalize_title(str((item.get("title") or [""])[0])) == expected
    ]
    if not exact_matches:
        return {
            "identity_status": "verify_failed",
            "identity_provider": provider,
            "identity_reason": "no exact normalized-title match",
        }
    if len(exact_matches) == 1:
        match = exact_matches[0]
    else:
        ranked = sorted(
            ((_crossref_identity_score(paper, item), item) for item in exact_matches),
            key=lambda pair: pair[0],
            reverse=True,
        )
        if ranked[0][0] == ranked[1][0]:
            return {
                "identity_status": "verify_failed",
                "identity_provider": provider,
                "identity_reason": "ambiguous exact-title matches",
            }
        match = ranked[0][1]
    date = (
        match.get("published-print")
        or match.get("published-online")
        or match.get("issued")
        or {}
    )
    parts = date.get("date-parts") or []
    venue = str((match.get("container-title") or [paper.get("venue") or ""])[0])
    candidate_year = parts[0][0] if parts and parts[0] else None
    year = candidate_year if isinstance(candidate_year, int) else paper.get("year")
    if not isinstance(year, int):
        year = _year_from_text(venue)
    authors = [
        " ".join(
            value
            for value in (str(author.get("given") or "").strip(), str(author.get("family") or "").strip())
            if value
        )
        for author in match.get("author") or []
        if isinstance(author, dict)
    ]
    doi = str(match.get("DOI") or "").strip()
    raw_abstract = str(match.get("abstract") or "").strip()
    abstract = html.unescape(re.sub(r"<[^>]+>", " ", raw_abstract))
    abstract = " ".join(abstract.split())
    return {
        "identity_status": "verified",
        "identity_provider": provider,
        "title": str((match.get("title") or [title])[0]),
        "authors": authors or list(paper.get("authors") or []),
        "year": year,
        "venue": venue,
        "doi": doi or None,
        "doi_or_stable_url": f"https://doi.org/{doi}" if doi else match.get("URL"),
        "publication_type": match.get("type"),
        "abstract": abstract or paper.get("abstract"),
        "abstract_source": "crossref" if abstract else paper.get("abstract_source"),
    }


def crossref_openalex_verify_metadata(
    paper: dict[str, Any],
    *,
    crossref_verify: MetadataVerifyCallable = crossref_verify_metadata,
    arxiv_provider: Callable[[str, ScholarQueryOptions], list[dict[str, Any]]] | None = None,
    fetch_json: JsonFetcher = _fetch_json,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Verify identity in Crossref, then fill a missing abstract by DOI from OpenAlex.

    OpenAlex is metadata enrichment, not a second discovery query. Failure to
    reach it does not erase a valid Crossref identity; downstream screening
    still refuses to treat a snippet as an abstract.
    """

    result = dict(crossref_verify(paper))
    arxiv_hint = "arxiv" in " ".join(
        str(paper.get(key) or "").casefold()
        for key in ("venue", "doi_or_stable_url", "arxiv_id")
    )
    if arxiv_hint and (
        result.get("identity_status") != "verified"
        or not str(result.get("abstract") or "").strip()
    ):
        provider = arxiv_provider or arxiv_search
        title = str(paper.get("title") or "").strip()
        year = paper.get("year")
        try:
            rows = provider(
                title,
                ScholarQueryOptions(
                    year_from=year - 1 if isinstance(year, int) else None,
                    year_to=year + 1 if isinstance(year, int) else None,
                    exact_title=True,
                    page=1,
                ),
            )
        except (ProviderUnavailable, OSError, ValueError, urllib.error.URLError):
            rows = []
        expected = _normalize_title(title)
        exact = [
            row
            for row in rows
            if _normalize_title(str(row.get("title") or "")) == expected
            and row.get("identity_status") == "verified"
        ]
        if exact:
            row = exact[0]
            return {
                "identity_status": "verified",
                "identity_provider": "arxiv",
                "identity_reason": "exact normalized-title match",
                "title": row.get("title"),
                "authors": row.get("authors") or paper.get("authors") or [],
                "year": row.get("year") or year,
                "venue": "arXiv preprint",
                "doi": None,
                "doi_or_stable_url": row.get("doi_or_stable_url"),
                "publication_type": "preprint",
                "abstract": row.get("snippet"),
                "abstract_source": "arxiv",
                "arxiv_id": row.get("arxiv_id"),
            }
    if result.get("identity_status") != "verified" or str(
        result.get("abstract") or ""
    ).strip():
        return result
    doi = str(result.get("doi") or paper.get("doi") or "").strip()
    if not doi:
        return result
    url = "https://api.openalex.org/works/" + urllib.parse.quote(
        f"https://doi.org/{doi}", safe=""
    )
    try:
        payload = fetch_json(
            url,
            timeout,
            {"Accept": "application/json", "User-Agent": "ARIS-research-lit/2.0"},
        )
    except (OSError, ValueError, urllib.error.URLError, ProviderUnavailable):
        return result
    inverted = payload.get("abstract_inverted_index") if isinstance(payload, dict) else None
    if not isinstance(inverted, dict):
        return result
    positioned: list[tuple[int, str]] = []
    for token, positions in inverted.items():
        if not isinstance(token, str) or not isinstance(positions, list):
            continue
        positioned.extend(
            (position, token) for position in positions if isinstance(position, int)
        )
    abstract = " ".join(token for _, token in sorted(positioned))
    if abstract:
        result["abstract"] = abstract
        result["abstract_source"] = "openalex"
    return result


def _paper_keys(row: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    doi = str(row.get("doi") or "").strip().casefold()
    if not doi:
        stable = str(row.get("doi_or_stable_url") or "")
        match = re.search(r"(?:doi\.org/|doi:)(10\.\d{4,9}/\S+)", stable, re.I)
        doi = match.group(1).rstrip(".,)").casefold() if match else ""
    if doi:
        keys.add(f"doi:{doi}")
    arxiv_id = str(row.get("arxiv_id") or "").strip().casefold()
    if arxiv_id:
        keys.add(f"arxiv:{arxiv_id}")
    title = _normalize_title(str(row.get("title") or ""))
    if title:
        keys.add(f"title:{title}")
    return keys


def merge_and_deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge arXiv/IEEE discoveries without changing downstream admission rules."""

    merged: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    order: list[str] = []
    for candidate in rows:
        row = dict(candidate)
        candidate_keys = _paper_keys(row)
        key = next((aliases[item] for item in candidate_keys if item in aliases), None)
        if key is None:
            key = next(iter(sorted(candidate_keys)), f"provider:{row.get('paper_id')}")
        provider = str(row.get("discovery_provider") or "")
        if key not in merged:
            row["discovery_providers"] = [provider] if provider else []
            merged[key] = row
            order.append(key)
            for alias in candidate_keys:
                aliases[alias] = key
            continue
        current = merged[key]
        for alias in candidate_keys:
            aliases[alias] = key
        providers = list(current.get("discovery_providers") or [])
        if provider and provider not in providers:
            providers.append(provider)
        current["discovery_providers"] = providers
        for name, value in row.items():
            if name == "discovery_providers":
                continue
            if current.get(name) in (None, "", [], {}) and value not in (None, "", [], {}):
                current[name] = value
        if provider == "ieee_xplore":
            for name in ("venue", "citation_count", "doi", "doi_or_stable_url"):
                if row.get(name) not in (None, ""):
                    current[name] = row[name]
    return [merged[key] for key in order]


def _scholar_params(query: str, options: ScholarQueryOptions) -> dict[str, str | int]:
    effective_query = f'"{query}"' if options.exact_title else query
    params: dict[str, str | int] = {
        "q": effective_query,
        "start": max(0, options.page - 1) * options.page_size,
        "num": options.page_size,
    }
    if options.year_from is not None:
        params["as_ylo"] = options.year_from
    if options.year_to is not None:
        params["as_yhi"] = options.year_to
    if options.cited_by:
        params["cites"] = options.cited_by
    return params


def _query_options_payload(options: ScholarQueryOptions) -> dict[str, Any]:
    """Persist the requested constraints with an auditable human fallback."""

    return {
        "year_from": options.year_from,
        "year_to": options.year_to,
        "exact_title": options.exact_title,
        "page": options.page,
        "cited_by": options.cited_by,
        "page_size": options.page_size,
    }


def _within_requested_year(row: dict[str, Any], options: ScholarQueryOptions) -> bool:
    year = row.get("year")
    if options.year_from is not None and (not isinstance(year, int) or year < options.year_from):
        return False
    if options.year_to is not None and (not isinstance(year, int) or year > options.year_to):
        return False
    return True


def _matches_exact_title(row: dict[str, Any], query: str, options: ScholarQueryOptions) -> bool:
    if not options.exact_title:
        return True
    return str(row.get("title") or "").casefold().strip() == query.casefold().strip()


def _scholar_row(item: dict[str, Any], provider: str) -> dict[str, Any]:
    publication = item.get("publication_info") or {}
    summary = str(publication.get("summary") or "")
    inline = item.get("inline_links") or {}
    cited = inline.get("cited_by") or {}
    authors = publication.get("authors") or []
    return {
        "paper_id": str(item.get("result_id") or item.get("link") or item.get("title") or ""),
        "title": str(item.get("title") or ""),
        "authors": [str(author.get("name")) for author in authors if author.get("name")],
        "year": _year_from_text(summary),
        "venue": summary,
        "doi_or_stable_url": item.get("link"),
        "citation_count": cited.get("total"),
        "cited_by_id": cited.get("cites_id"),
        "cited_by_url": cited.get("link"),
        "snippet": item.get("snippet"),
        "identity_status": "verify_pending",
        "discovery_provider": provider,
    }


def serpapi_google_scholar_search(
    query: str,
    options: ScholarQueryOptions,
    *,
    api_key: str | None = None,
    timeout: float = 30,
    fetch_json: JsonFetcher = _fetch_json,
) -> list[dict[str, Any]]:
    provider = "serpapi_google_scholar"
    key = (api_key if api_key is not None else os.getenv("SERPAPI_KEY", "")).strip()
    if not key:
        raise ProviderUnavailable(provider, "SERPAPI_KEY is missing")
    params = {"engine": "google_scholar", "api_key": key, **_scholar_params(query, options)}
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    try:
        payload = fetch_json(url, timeout, {"Accept": "application/json"})
    except urllib.error.HTTPError as exc:
        if exc.code == 400:
            raise ValueError("SerpApi rejected the Scholar query") from exc
        raise _provider_network_error(provider, exc) from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise _provider_network_error(provider, exc) from exc
    except (json.JSONDecodeError, UnicodeError, ValueError) as exc:
        raise ProviderUnavailable(provider, "invalid service response") from exc
    error = str(payload.get("error") or "").strip()
    if error:
        folded = error.casefold()
        if any(token in folded for token in ("api key", "account", "quota", "credit", "rate limit")):
            raise ProviderUnavailable(provider, "authentication or quota failure")
        raise ValueError(f"SerpApi rejected the Scholar query: {error}")
    organic = payload.get("organic_results") or []
    if not isinstance(organic, list):
        raise ProviderUnavailable(provider, "malformed service response")
    return [_scholar_row(item, provider) for item in organic if isinstance(item, dict)]


def scholar_google_hk_search(
    query: str,
    options: ScholarQueryOptions,
    *,
    browser_search: Callable[[str, ScholarQueryOptions], list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Use the bounded visible-browser adapter, or an explicitly injected one."""

    if browser_search is not None:
        return browser_search(query, options)
    try:
        # The browser adapter deliberately follows Scholar's normal ten-result
        # result pages. ``page_size`` remains a SerpApi-only capability.
        return browser_scholar_search(
            query,
            page=options.page,
            year_from=options.year_from,
            year_to=options.year_to,
            exact_title=options.exact_title,
            cited_by=options.cited_by,
        )
    except BrowserScholarError as exc:
        raise ProviderUnavailable(
            "scholar_google_hk", str(exc), blocked=exc.blocked
        ) from exc


def arxiv_search(
    query: str,
    options: ScholarQueryOptions,
    *,
    timeout: float = 30,
    fetch_text: TextFetcher = _fetch_text,
) -> list[dict[str, Any]]:
    provider = "arxiv"
    if options.cited_by:
        raise ProviderUnavailable(
            provider,
            "the cited-by constraint is only available from Google Scholar",
        )
    terms = [f'ti:"{query}"' if options.exact_title else f'all:"{query}"']
    if options.year_from is not None or options.year_to is not None:
        lower = f"{options.year_from or 1900:04d}0101000000"
        upper = f"{options.year_to or 9999:04d}1231235959"
        terms.append(f"submittedDate:[{lower} TO {upper}]")
    expression = " AND ".join(terms)
    params = {
        "search_query": expression,
        "start": max(0, options.page - 1) * options.page_size,
        "max_results": options.page_size,
    }
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    try:
        xml = fetch_text(url, timeout, {"User-Agent": "ARIS/1.0"})
        root = ET.fromstring(xml)
    except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise _provider_network_error(provider, exc) from exc
    except UnicodeError as exc:
        raise ProviderUnavailable(provider, "invalid service response") from exc
    except ET.ParseError as exc:
        raise ProviderUnavailable(provider, "invalid service response") from exc
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    rows: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        published = entry.findtext("atom:published", default="", namespaces=ns)
        year = _year_from_text(published)
        if options.year_from is not None and (year is None or year < options.year_from):
            continue
        if options.year_to is not None and (year is None or year > options.year_to):
            continue
        stable_url = entry.findtext("atom:id", default="", namespaces=ns)
        arxiv_id = stable_url.rstrip("/").split("/")[-1].split("v")[0]
        title = " ".join(entry.findtext("atom:title", default="", namespaces=ns).split())
        rows.append(
            {
                "paper_id": f"arxiv:{arxiv_id}",
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": [
                    author.findtext("atom:name", default="", namespaces=ns)
                    for author in entry.findall("atom:author", ns)
                ],
                "year": year,
                "venue": "arXiv preprint",
                "doi_or_stable_url": stable_url,
                "citation_count": None,
                "snippet": " ".join(
                    entry.findtext("atom:summary", default="", namespaces=ns).split()
                ),
                "identity_status": "verified" if arxiv_id else "verify_pending",
                "discovery_provider": provider,
            }
        )
    return rows


def ieee_xplore_search(
    query: str,
    options: ScholarQueryOptions,
    *,
    browser_search: Callable[..., list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Read one public IEEE Xplore page through the bounded visible browser."""

    if options.cited_by:
        raise ProviderUnavailable(
            "ieee_xplore",
            "the cited-by constraint is only available from Google Scholar",
        )
    try:
        if browser_search is not None:
            rows = browser_search(query, page=options.page, exact_title=options.exact_title)
        else:
            rows = browser_ieee_search(
                query, page=options.page, exact_title=options.exact_title
            )
        return [
            row
            for row in rows
            if _within_requested_year(row, options)
            and _matches_exact_title(row, query, options)
        ]
    except BrowserIeeeError as exc:
        raise ProviderUnavailable("ieee_xplore", str(exc), blocked=exc.blocked) from exc


def research_literature_search(
    query: str,
    options: ScholarQueryOptions | None = None,
    *,
    serpapi_key: str | None = None,
    serpapi_search: Callable[[str, ScholarQueryOptions], list[dict[str, Any]]] | None = None,
    scholar_search: Callable[[str, ScholarQueryOptions], list[dict[str, Any]]] | None = None,
    arxiv_provider: Callable[[str, ScholarQueryOptions], list[dict[str, Any]]] | None = None,
    ieee_provider: Callable[[str, ScholarQueryOptions], list[dict[str, Any]]] | None = None,
) -> SearchOutcome:
    """Apply the fixed research-lit provider cascade and no other discovery route."""

    selected = options or ScholarQueryOptions()
    attempts: list[dict[str, str]] = []
    # A source incident is intentionally scoped to one query. Retrying a normal
    # later query is safer than permanently suppressing a source after a
    # transient network failure or an anti-automation page.
    serpapi = serpapi_search or (
        lambda value, opts: serpapi_google_scholar_search(
            value, opts, api_key=serpapi_key
        )
    )
    direct_scholar = scholar_search or (
        lambda value, opts: scholar_google_hk_search(value, opts)
    )
    arxiv_gateway = arxiv_provider or arxiv_search
    ieee_gateway = ieee_provider or ieee_xplore_search

    try:
        results = serpapi(query, selected)
    except ProviderUnavailable as exc:
        attempts.append(exc.attempt())
    else:
        attempts.append({"provider": "serpapi_google_scholar", "status": "complete", "reason": ""})
        return SearchOutcome(
            results,
            "serpapi_google_scholar",
            True,
            attempts,
            _query_options_payload(selected),
        )

    try:
        results = direct_scholar(query, selected)
    except ProviderUnavailable as exc:
        attempts.append(exc.attempt())
    else:
        attempts.append({"provider": "scholar_google_hk", "status": "complete", "reason": ""})
        return SearchOutcome(
            results,
            "scholar_google_hk",
            True,
            attempts,
            _query_options_payload(selected),
        )

    fallback_rows: list[dict[str, Any]] = []
    fallback_successes: list[str] = []
    providers = (("arxiv", arxiv_gateway), ("ieee_xplore", ieee_gateway))
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="aris-discovery") as executor:
        futures = {
            provider_name: executor.submit(provider, query, selected)
            for provider_name, provider in providers
        }
        for provider_name, _ in providers:
            future = futures[provider_name]
            try:
                rows = future.result()
            except ProviderUnavailable as exc:
                attempts.append(exc.attempt())
            else:
                fallback_successes.append(provider_name)
                attempts.append({"provider": provider_name, "status": "complete", "reason": ""})
                fallback_rows.extend(rows)
    if fallback_successes:
        return SearchOutcome(
            merge_and_deduplicate(fallback_rows),
            "+".join(fallback_successes),
            False,
            attempts,
            _query_options_payload(selected),
        )
    raise HumanSearchRequired(attempts, query_options=_query_options_payload(selected))
