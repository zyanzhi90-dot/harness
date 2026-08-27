from arisctl import browser_scholar
from arisctl.browser_scholar import normalize_scholar_result, parse_year_venue


def test_parse_year_venue_accepts_scholar_nonbreaking_spaces() -> None:
    year, venue = parse_year_venue(
        "FJ Abu-Dakka, M Saveriano\u00a0- Frontiers in Robotics and AI, 2020 - frontiersin.org"
    )
    assert year == 2020
    assert venue == "Frontiers in Robotics and AI"


def test_normalize_visible_scholar_card_preserves_google_scholar_provenance() -> None:
    row = normalize_scholar_result(
        {
            "title": "Visible Scholar Paper",
            "link": "https://example.test/paper",
            "year_venue_raw": "A Author - Test Venue, 2024 - example.test",
            "citation_count": 17,
            "cited_by_url": "https://scholar.google.hk/scholar?cites=123&hl=en",
            "snippet": "Visible result text",
        }
    )
    assert row["paper_id"] == "scholar:123"
    assert row["year"] == 2024
    assert row["venue"] == "Test Venue"
    assert row["citation_count"] == 17
    assert row["citation_source"] == "google_scholar"
    assert row["discovery_provider"] == "scholar_google_hk"


def test_browser_search_serializes_calls_with_ten_second_cooldown(monkeypatch) -> None:
    clocks = iter((100.0, 110.0))
    sleeps: list[float] = []
    monkeypatch.setattr(browser_scholar.time, "monotonic", lambda: next(clocks))
    monkeypatch.setattr(browser_scholar.time, "sleep", sleeps.append)
    monkeypatch.setattr(browser_scholar, "_LAST_SEARCH_FINISHED", 95.0)
    monkeypatch.setattr(
        browser_scholar,
        "_search_google_scholar_once",
        lambda query, *, page, **kwargs: [{"title": query, "page": page}],
    )

    assert browser_scholar.search_google_scholar("topic", page=2) == [{"title": "topic", "page": 2}]
    assert sleeps == [5.0]
    assert browser_scholar._LAST_SEARCH_FINISHED == 110.0


def test_scholar_url_preserves_normal_advanced_search_constraints() -> None:
    url = browser_scholar._scholar_url(
        "Exact Paper",
        2,
        year_from=2020,
        year_to=2025,
        exact_title=True,
        cited_by="123",
    )
    assert "start=10" in url
    assert "as_ylo=2020" in url
    assert "as_yhi=2025" in url
    assert "cites=123" in url
    assert "q=%22Exact+Paper%22" in url
