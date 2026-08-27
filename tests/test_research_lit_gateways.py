from __future__ import annotations

import inspect
import hashlib
import json
import threading
import urllib.parse
from pathlib import Path

import pytest

from arisctl import gateways
from arisctl.gateways import (
    FullTextPayload,
    HumanSearchRequired,
    ProviderUnavailable,
    ScholarQueryOptions,
    crossref_openalex_verify_metadata,
    crossref_verify_metadata,
    crossref_declared_fulltext,
    openalex_open_access_fulltext,
    open_access_fulltext,
    research_literature_search,
    semantic_scholar_open_access_fulltext,
    scholar_google_hk_search,
    serpapi_google_scholar_search,
    append_jsonl,
    repair_embedded_record_hash_contamination,
)


def test_jsonl_writer_strips_stale_receipts_and_narrow_repair_recovers_legacy_defect(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "registry.jsonl"
    append_jsonl(registry, {"source_id": "P1", "value": 1})
    first = json.loads(registry.read_text(encoding="utf-8").splitlines()[0])
    append_jsonl(registry, {**first, "value": 2})
    second = json.loads(registry.read_text(encoding="utf-8").splitlines()[1])
    unhashed = dict(second)
    recorded = unhashed.pop("record_sha256")
    assert hashlib.sha256(
        json.dumps(unhashed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest() == recorded

    legacy = {**second, "value": 3, "previous_record_sha256": recorded}
    legacy_hash_input = dict(legacy)
    legacy["record_sha256"] = hashlib.sha256(
        json.dumps(
            legacy_hash_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(legacy, ensure_ascii=False, sort_keys=True) + "\n")

    result = repair_embedded_record_hash_contamination(registry)
    assert result["contaminated_rows"] == [3]
    previous = None
    for row in map(json.loads, registry.read_text(encoding="utf-8").splitlines()):
        assert row["previous_record_sha256"] == previous
        recorded = row["record_sha256"]
        unhashed = dict(row)
        unhashed.pop("record_sha256")
        assert hashlib.sha256(
            json.dumps(
                unhashed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest() == recorded
        previous = recorded


def test_open_access_fulltext_resolves_admitted_doi_and_requires_real_pdf() -> None:
    captured: dict[str, str] = {}

    def fetch_json(url: str, timeout: float, headers: dict[str, str]) -> dict:
        captured["metadata_url"] = url
        return {
            "title": "Exact Robot Paper",
            "externalIds": {"DOI": "10.1000/exact"},
            "openAccessPdf": {"url": "https://repository.test/exact.pdf"},
        }

    payload = semantic_scholar_open_access_fulltext(
        {"doi": "10.1000/exact", "title": "Exact Robot Paper"},
        fetch_json=fetch_json,
        fetch_bytes=lambda url, timeout, headers: b"%PDF-1.7\nreal bytes",
    )
    assert "DOI:10.1000%2Fexact" in captured["metadata_url"]
    assert payload.content.startswith(b"%PDF-")
    assert payload.source_url == "https://repository.test/exact.pdf"

    with pytest.raises(ProviderUnavailable, match="not a PDF"):
        semantic_scholar_open_access_fulltext(
            {"doi": "10.1000/exact"},
            fetch_json=fetch_json,
            fetch_bytes=lambda url, timeout, headers: b"<html>paywall</html>",
        )


def test_crossref_fulltext_uses_only_declared_supported_objects() -> None:
    payload = crossref_declared_fulltext(
        {"doi": "10.1000/exact"},
        fetch_json=lambda url, timeout, headers: {
            "message": {
                "link": [
                    {"URL": "https://publisher.test/landing", "content-type": "text/html"},
                    {"URL": "https://publisher.test/paper.pdf", "content-type": "application/pdf"},
                ]
            }
        },
        fetch_bytes=lambda url, timeout, headers: b"%PDF-1.7\nreal bytes",
    )
    assert payload.provider == "crossref_declared_fulltext"
    assert payload.source_url.endswith("paper.pdf")

    with pytest.raises(ProviderUnavailable, match="no supported full-text"):
        crossref_declared_fulltext(
            {"doi": "10.1000/exact"},
            fetch_json=lambda url, timeout, headers: {
                "message": {"link": [{"URL": "https://publisher.test", "content-type": "text/html"}]}
            },
        )


def test_openalex_fulltext_requires_matching_doi_and_real_pdf() -> None:
    payload = openalex_open_access_fulltext(
        {"doi": "10.1000/exact"},
        fetch_json=lambda url, timeout, headers: {
            "doi": "https://doi.org/10.1000/exact",
            "best_oa_location": {"pdf_url": "https://repository.test/exact.pdf"},
        },
        fetch_bytes=lambda url, timeout, headers: b"%PDF-1.7\nreal bytes",
    )
    assert payload.provider == "openalex_open_access"

    with pytest.raises(ProviderUnavailable, match="DOI did not match"):
        openalex_open_access_fulltext(
            {"doi": "10.1000/exact"},
            fetch_json=lambda url, timeout, headers: {
                "doi": "https://doi.org/10.1000/other",
                "best_oa_location": {"pdf_url": "https://repository.test/other.pdf"},
            },
        )


def test_crossref_metadata_verification_requires_exact_title_match() -> None:
    paper = {"title": "Exact Robot Paper", "year": 2020, "authors": ["A"]}

    def fetch(url: str, timeout: float, headers: dict[str, str]) -> dict:
        return {
            "message": {
                "items": [
                    {
                        "DOI": "10.1000/exact",
                        "title": ["Exact Robot Paper"],
                        "author": [{"given": "Ada", "family": "Lovelace"}],
                        "published-online": {"date-parts": [[2021, 1, 2]]},
                        "container-title": ["IEEE Transactions on Robotics"],
                        "URL": "https://doi.org/10.1000/exact",
                        "type": "journal-article",
                    }
                ]
            }
        }

    verified = crossref_verify_metadata(paper, fetch_json=fetch)
    assert verified["identity_status"] == "verified"
    assert verified["doi"] == "10.1000/exact"
    assert verified["venue"] == "IEEE Transactions on Robotics"

    fallback_year = crossref_verify_metadata(
        {**paper, "year": None},
        fetch_json=lambda url, timeout, headers: {
            "message": {
                "items": [
                    {
                        "title": ["Exact Robot Paper"],
                        "published-online": {"date-parts": [[None]]},
                        "container-title": ["Proceedings of Robot Control 2020"],
                    }
                ]
            }
        },
    )
    assert fallback_year["year"] == 2020

    preserved_year = crossref_verify_metadata(
        paper,
        fetch_json=lambda url, timeout, headers: {
            "message": {
                "items": [
                    {
                        "title": ["Exact Robot Paper"],
                        "published-online": {"date-parts": [[None]]},
                        "container-title": ["Venue Without A Year"],
                    }
                ]
            }
        },
    )
    assert preserved_year["year"] == 2020

    failed = crossref_verify_metadata(
        paper,
        fetch_json=lambda url, timeout, headers: {
            "message": {"items": [{"title": ["Different Paper"]}]}
        },
    )
    assert failed["identity_status"] == "verify_failed"


def test_crossref_metadata_disambiguates_duplicate_titles_from_discovery_metadata() -> None:
    paper = {
        "title": "A Unified Robot Control Framework",
        "year": 2007,
        "authors": ["Ada Lovelace", "Grace Hopper"],
        "venue": "The International Journal of Robotics Research",
    }

    def fetch(url: str, timeout: float, headers: dict[str, str]) -> dict:
        return {
            "message": {
                "items": [
                    {
                        "DOI": "10.1000/book-version",
                        "title": ["A Unified Robot Control Framework"],
                        "author": [
                            {"given": "Ada", "family": "Lovelace"},
                            {"given": "Grace", "family": "Hopper"},
                        ],
                        "published-online": {"date-parts": [[2007]]},
                        "container-title": ["Springer Tracts in Robotics"],
                    },
                    {
                        "DOI": "10.1000/journal-version",
                        "title": ["A Unified Robot Control Framework"],
                        "author": [
                            {"given": "Ada", "family": "Lovelace"},
                            {"given": "Grace", "family": "Hopper"},
                        ],
                        "published-print": {"date-parts": [[2007]]},
                        "container-title": ["The International Journal of Robotics Research"],
                    },
                ]
            }
        }

    verified = crossref_verify_metadata(paper, fetch_json=fetch)
    assert verified["identity_status"] == "verified"
    assert verified["doi"] == "10.1000/journal-version"


def test_crossref_metadata_rejects_unresolved_duplicate_titles() -> None:
    paper = {"title": "Duplicate Robot Paper", "year": 2020}

    def fetch(url: str, timeout: float, headers: dict[str, str]) -> dict:
        return {
            "message": {
                "items": [
                    {"DOI": "10.1000/a", "title": ["Duplicate Robot Paper"]},
                    {"DOI": "10.1000/b", "title": ["Duplicate Robot Paper"]},
                ]
            }
        }

    result = crossref_verify_metadata(paper, fetch_json=fetch)
    assert result == {
        "identity_status": "verify_failed",
        "identity_provider": "crossref_metadata",
        "identity_reason": "ambiguous exact-title matches",
    }


def test_openalex_enrichment_reconstructs_missing_abstract_by_verified_doi() -> None:
    verified = {
        "identity_status": "verified",
        "identity_provider": "crossref_metadata",
        "title": "Exact Robot Paper",
        "doi": "10.1000/exact",
        "year": 2020,
    }
    calls: list[str] = []

    result = crossref_openalex_verify_metadata(
        {"title": "Exact Robot Paper"},
        crossref_verify=lambda paper: verified,
        fetch_json=lambda url, timeout, headers: (
            calls.append(url)
            or {"abstract_inverted_index": {"Impedance": [0], "control": [1]}}
        ),
    )

    assert calls and "api.openalex.org" in calls[0]
    assert result["abstract"] == "Impedance control"
    assert result["abstract_source"] == "openalex"


def test_arxiv_fallback_verifies_exact_title_and_supplies_abstract() -> None:
    result = crossref_openalex_verify_metadata(
        {
            "title": "Safe Impedance Learning",
            "year": 2025,
            "venue": "arXiv preprint arXiv:2501.12345",
        },
        crossref_verify=lambda paper: {
            "identity_status": "verify_failed",
            "identity_provider": "crossref_metadata",
        },
        arxiv_provider=lambda query, options: [
            {
                "title": "Safe Impedance Learning",
                "authors": ["A. Author"],
                "year": 2025,
                "doi_or_stable_url": "https://arxiv.org/abs/2501.12345",
                "arxiv_id": "2501.12345",
                "snippet": "A formal preprint abstract.",
                "identity_status": "verified",
            }
        ],
    )
    assert result["identity_status"] == "verified"
    assert result["identity_provider"] == "arxiv"
    assert result["abstract_source"] == "arxiv"


def test_open_access_fulltext_is_arxiv_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []
    direct = gateways.arxiv_declared_fulltext(
        {"arxiv_id": "2501.12345", "doi": "10.1000/exact"},
        fetch_bytes=lambda url, timeout, headers: requested.append(url) or b"%PDF-1.7\nbytes",
    )
    assert direct.source_url == "https://arxiv.org/pdf/2501.12345.pdf"
    assert requested == ["https://arxiv.org/pdf/2501.12345.pdf"]

    calls: list[str] = []

    def arxiv(paper: dict) -> FullTextPayload:
        calls.append("arxiv")
        if not paper.get("arxiv_id") and "arxiv.org/" not in str(
            paper.get("doi_or_stable_url") or ""
        ):
            raise ProviderUnavailable("arxiv_declared_fulltext", "admitted paper has no arXiv identity")
        return FullTextPayload(
            b"%PDF-1.7\nbytes",
            "https://arxiv.org/pdf/2501.12345.pdf",
            "application/pdf",
            "arxiv_declared_fulltext",
        )

    def forbidden(*args, **kwargs):
        raise AssertionError("non-arXiv full-text provider must not be called")

    monkeypatch.setattr(gateways, "arxiv_declared_fulltext", arxiv)
    monkeypatch.setattr(gateways, "crossref_declared_fulltext", forbidden)
    monkeypatch.setattr(gateways, "openalex_open_access_fulltext", forbidden)
    monkeypatch.setattr(gateways, "semantic_scholar_open_access_fulltext", forbidden)

    payload = open_access_fulltext({"arxiv_id": "2501.12345", "doi": "10.1000/exact"})
    assert payload.provider == "arxiv_declared_fulltext"
    with pytest.raises(ProviderUnavailable, match="no arXiv identity"):
        open_access_fulltext({"doi": "10.1000/exact"})
    assert calls == ["arxiv", "arxiv"]


def test_identity_and_fulltext_providers_are_not_discovery_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden_calls: list[str] = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append("called")
        raise AssertionError("identity/retrieval provider used for discovery")

    monkeypatch.setattr(gateways, "crossref_verify_metadata", forbidden)
    monkeypatch.setattr(gateways, "crossref_declared_fulltext", forbidden)
    monkeypatch.setattr(gateways, "openalex_open_access_fulltext", forbidden)
    monkeypatch.setattr(gateways, "semantic_scholar_open_access_fulltext", forbidden)
    outcome = research_literature_search(
        "topic",
        serpapi_search=lambda query, options: [
            {
                "paper_id": "S1",
                "title": "Scholar-discovered paper",
                "discovery_provider": "serpapi_google_scholar",
            }
        ],
        scholar_search=forbidden,
        arxiv_provider=forbidden,
        ieee_provider=forbidden,
    )
    assert outcome.provider == "serpapi_google_scholar"
    assert outcome.results[0]["discovery_provider"] == "serpapi_google_scholar"
    assert forbidden_calls == []


def unavailable(provider: str, *, blocked: bool = False):
    def search(query: str, options: ScholarQueryOptions):
        raise ProviderUnavailable(provider, "test failure", blocked=blocked)

    return search


def test_serpapi_zero_results_is_success_and_does_not_fallback() -> None:
    calls: list[str] = []

    def serpapi(query: str, options: ScholarQueryOptions) -> list[dict]:
        calls.append("serpapi")
        return []

    outcome = research_literature_search(
        "empty query",
        serpapi_search=serpapi,
        scholar_search=lambda query, options: calls.append("scholar") or [],
        arxiv_provider=lambda query, options: calls.append("arxiv") or [],
        ieee_provider=lambda query, options: calls.append("ieee") or [],
    )

    assert outcome.provider == "serpapi_google_scholar"
    assert outcome.results == []
    assert outcome.google_scholar_coverage is True
    assert calls == ["serpapi"]


def test_fixed_fallback_reaches_direct_scholar_only_after_serpapi_failure() -> None:
    calls: list[str] = []

    def scholar(query: str, options: ScholarQueryOptions) -> list[dict]:
        calls.append("scholar")
        return [{"paper_id": "S1", "title": "Scholar paper"}]

    outcome = research_literature_search(
        "topic",
        serpapi_search=unavailable("serpapi_google_scholar"),
        scholar_search=scholar,
        arxiv_provider=lambda query, options: calls.append("arxiv") or [],
        ieee_provider=lambda query, options: calls.append("ieee") or [],
    )

    assert outcome.provider == "scholar_google_hk"
    assert outcome.google_scholar_coverage is True
    assert calls == ["scholar"]


def test_arxiv_and_ieee_are_combined_and_deduplicated_after_both_scholar_failures() -> None:
    arxiv_row = {
        "paper_id": "arxiv:1234.5678",
        "arxiv_id": "1234.5678",
        "title": "The Same Paper",
        "venue": "arXiv preprint",
        "citation_count": None,
        "discovery_provider": "arxiv",
    }
    ieee_row = {
        "paper_id": "doi:10.1109/test",
        "arxiv_id": "1234.5678",
        "title": "The Same Paper",
        "venue": "IEEE Test",
        "citation_count": 42,
        "doi": "10.1109/test",
        "discovery_provider": "ieee_xplore",
    }
    outcome = research_literature_search(
        "topic",
        serpapi_search=unavailable("serpapi_google_scholar"),
        scholar_search=unavailable("scholar_google_hk", blocked=True),
        arxiv_provider=lambda query, options: [arxiv_row],
        ieee_provider=lambda query, options: [ieee_row],
    )

    assert outcome.provider == "arxiv+ieee_xplore"
    assert outcome.google_scholar_coverage is False
    assert len(outcome.results) == 1
    assert outcome.results[0]["venue"] == "IEEE Test"
    assert outcome.results[0]["citation_count"] == 42
    assert outcome.results[0]["discovery_providers"] == ["arxiv", "ieee_xplore"]


def test_level_three_sources_run_in_parallel() -> None:
    lock = threading.Lock()
    arrivals = 0
    both_started = threading.Event()
    waited: list[bool] = []

    def provider(name: str):
        def search(query: str, options: ScholarQueryOptions) -> list[dict]:
            nonlocal arrivals
            with lock:
                arrivals += 1
                if arrivals == 2:
                    both_started.set()
            waited.append(both_started.wait(timeout=0.5))
            return [{"paper_id": name, "title": name, "discovery_provider": name}]

        return search

    outcome = research_literature_search(
        "topic",
        serpapi_search=unavailable("serpapi_google_scholar"),
        scholar_search=unavailable("scholar_google_hk"),
        arxiv_provider=provider("arxiv"),
        ieee_provider=provider("ieee_xplore"),
    )
    assert outcome.provider == "arxiv+ieee_xplore"
    assert waited == [True, True]


def test_one_level_three_provider_can_succeed_alone() -> None:
    outcome = research_literature_search(
        "topic",
        serpapi_search=unavailable("serpapi_google_scholar"),
        scholar_search=unavailable("scholar_google_hk"),
        arxiv_provider=lambda query, options: [],
        ieee_provider=unavailable("ieee_xplore"),
    )
    assert outcome.provider == "arxiv"
    assert outcome.results == []


def test_gateway_has_no_run_wide_provider_suppression_parameter() -> None:
    calls: list[str] = []
    outcome = research_literature_search(
        "topic",
        serpapi_search=lambda query, options: calls.append("serpapi") or [],
        scholar_search=lambda query, options: calls.append("scholar") or [],
        arxiv_provider=lambda query, options: calls.append("arxiv") or [],
        ieee_provider=unavailable("ieee_xplore"),
    )
    assert outcome.provider == "serpapi_google_scholar"
    assert calls == ["serpapi"]
    assert "unavailable_providers" not in inspect.signature(research_literature_search).parameters


def test_all_four_routes_unavailable_requires_human_search() -> None:
    with pytest.raises(HumanSearchRequired) as raised:
        research_literature_search(
            "topic",
            serpapi_search=unavailable("serpapi_google_scholar"),
            scholar_search=unavailable("scholar_google_hk", blocked=True),
            arxiv_provider=unavailable("arxiv"),
            ieee_provider=unavailable("ieee_xplore"),
        )
    assert [item["provider"] for item in raised.value.attempts] == [
        "serpapi_google_scholar",
        "scholar_google_hk",
        "arxiv",
        "ieee_xplore",
    ]


def test_serpapi_uses_google_scholar_key_and_scholar_query_capabilities() -> None:
    captured: dict[str, object] = {}

    def fetch(url: str, timeout: float, headers: dict[str, str]) -> dict:
        captured["url"] = url
        return {
            "organic_results": [
                {
                    "result_id": "R1",
                    "title": "Exact Paper",
                    "link": "https://example.test/paper",
                    "publication_info": {
                        "summary": "A. Author - Test Venue, 2024",
                        "authors": [{"name": "A. Author"}],
                    },
                    "inline_links": {
                        "cited_by": {"total": 17, "cites_id": "C1", "link": "https://example.test/cited"}
                    },
                }
            ]
        }

    rows = serpapi_google_scholar_search(
        "Exact Paper",
        ScholarQueryOptions(
            year_from=2020,
            year_to=2025,
            exact_title=True,
            page=3,
            cited_by="CLUSTER",
        ),
        api_key="secret-test-key",
        fetch_json=fetch,
    )
    params = urllib.parse.parse_qs(urllib.parse.urlparse(str(captured["url"])).query)
    assert params["engine"] == ["google_scholar"]
    assert params["api_key"] == ["secret-test-key"]
    assert params["q"] == ['"Exact Paper"']
    assert params["as_ylo"] == ["2020"]
    assert params["as_yhi"] == ["2025"]
    assert params["start"] == ["40"]
    assert params["cites"] == ["CLUSTER"]
    assert rows[0]["citation_count"] == 17
    assert rows[0]["cited_by_id"] == "C1"


def test_direct_scholar_uses_bounded_browser_adapter_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def browser(query: str, *, page: int, **kwargs: object) -> list[dict]:
        captured.update(query=query, page=page, **kwargs)
        return [{"paper_id": "S1", "title": "Browser result"}]

    monkeypatch.setattr(gateways, "browser_scholar_search", browser)
    assert scholar_google_hk_search("topic", ScholarQueryOptions(page=3)) == [
        {"paper_id": "S1", "title": "Browser result"}
    ]
    assert captured == {
        "query": "topic",
        "page": 3,
        "year_from": None,
        "year_to": None,
        "exact_title": False,
        "cited_by": None,
    }

    rows = scholar_google_hk_search(
        "topic",
        ScholarQueryOptions(),
        browser_search=lambda query, options: [
            {"paper_id": "S1", "title": "Browser result"}
        ],
    )
    assert rows == [{"paper_id": "S1", "title": "Browser result"}]


def test_direct_scholar_maps_a_visible_browser_block_to_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arisctl.browser_scholar import BrowserScholarError

    def blocked(query: str, *, page: int, **kwargs: object) -> list[dict]:
        raise BrowserScholarError("Scholar displayed a block or CAPTCHA page", blocked=True)

    monkeypatch.setattr(gateways, "browser_scholar_search", blocked)
    with pytest.raises(ProviderUnavailable, match="CAPTCHA") as raised:
        scholar_google_hk_search("topic", ScholarQueryOptions())
    assert raised.value.blocked is True


def test_ieee_uses_bounded_browser_adapter_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("IEEE_XPLORE_API_KEY", "must-not-be-used")

    def browser(query: str, *, page: int, **kwargs: object) -> list[dict]:
        captured.update(query=query, page=page, **kwargs)
        return [{"paper_id": "ieee:1", "title": "Visible IEEE result"}]

    monkeypatch.setattr(gateways, "browser_ieee_search", browser)
    rows = gateways.ieee_xplore_search("topic", ScholarQueryOptions(page=3))
    assert rows == [{"paper_id": "ieee:1", "title": "Visible IEEE result"}]
    assert captured == {"query": "topic", "page": 3, "exact_title": False}


def test_ieee_browser_block_maps_to_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arisctl.browser_ieee import BrowserIeeeError

    def blocked(query: str, *, page: int, **kwargs: object) -> list[dict]:
        raise BrowserIeeeError("IEEE Xplore displayed a block or CAPTCHA page", blocked=True)

    monkeypatch.setattr(gateways, "browser_ieee_search", blocked)
    with pytest.raises(ProviderUnavailable, match="CAPTCHA") as raised:
        gateways.ieee_xplore_search("topic", ScholarQueryOptions())
    assert raised.value.blocked is True


def test_ieee_applies_visible_year_and_exact_title_filters() -> None:
    rows = gateways.ieee_xplore_search(
        "Exact Paper",
        ScholarQueryOptions(year_from=2024, year_to=2024, exact_title=True),
        browser_search=lambda query, **kwargs: [
            {"paper_id": "I1", "title": "Exact Paper", "year": 2024},
            {"paper_id": "I2", "title": "Exact Paper", "year": 2023},
            {"paper_id": "I3", "title": "Related Paper", "year": 2024},
        ],
    )
    assert [row["paper_id"] for row in rows] == ["I1"]


def test_cited_by_constraint_does_not_silently_degrade_on_level_three_sources() -> None:
    with pytest.raises(HumanSearchRequired) as raised:
        research_literature_search(
            "topic",
            ScholarQueryOptions(cited_by="cluster"),
            serpapi_search=unavailable("serpapi_google_scholar"),
            scholar_search=unavailable("scholar_google_hk"),
        )
    reasons = {item["provider"]: item["reason"] for item in raised.value.attempts}
    assert "cited-by constraint" in reasons["arxiv"]
    assert "cited-by constraint" in reasons["ieee_xplore"]
