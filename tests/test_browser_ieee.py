from arisctl import browser_ieee
from arisctl.browser_ieee import normalize_ieee_result, parse_year_venue


def test_parse_year_venue_reads_visible_ieee_card() -> None:
    year, venue = parse_year_venue(
        "Learning Variable Impedance Control\nIEEE Transactions on Robotics\n2021"
    )
    assert year == 2021
    assert venue == "IEEE Transactions on Robotics"

    conference_year, conference_venue = parse_year_venue(
        "Visible paper\n2023 IEEE Conference on Robot Control\nYear: 2023 | Conference Paper"
    )
    assert conference_year == 2023
    assert conference_venue == "2023 IEEE Conference on Robot Control"


def test_normalize_visible_ieee_card_keeps_browser_provenance() -> None:
    row = normalize_ieee_result(
        {
            "title": "Visible IEEE Paper",
            "link": "https://ieeexplore.ieee.org/document/9361101/",
            "metadata_raw": "Visible IEEE Paper\nIEEE Transactions on Robotics\n2021",
            "citation_count": 12,
            "snippet": "Visible result text",
        }
    )
    assert row["paper_id"] == "ieee:9361101"
    assert row["year"] == 2021
    assert row["venue"] == "IEEE Transactions on Robotics"
    assert row["citation_count"] == 12
    assert row["discovery_provider"] == "ieee_xplore"
    assert row["retrieval_method"] == "visible_browser"


def test_browser_search_serializes_calls_with_fifteen_second_cooldown(monkeypatch) -> None:
    clocks = iter((100.0, 115.0))
    sleeps: list[float] = []
    monkeypatch.setattr(browser_ieee.time, "monotonic", lambda: next(clocks))
    monkeypatch.setattr(browser_ieee.time, "sleep", sleeps.append)
    monkeypatch.setattr(browser_ieee, "_LAST_SEARCH_FINISHED", 90.0)
    monkeypatch.setattr(
        browser_ieee,
        "_search_ieee_once",
        lambda query, *, page, **kwargs: [{"title": query, "page": page}],
    )

    assert browser_ieee.search_ieee_xplore("topic", page=2) == [{"title": "topic", "page": 2}]
    assert sleeps == [5.0]
    assert browser_ieee._LAST_SEARCH_FINISHED == 115.0


def test_ieee_url_uses_a_normal_quoted_query_for_exact_title() -> None:
    assert "queryText=%22Exact+Paper%22" in browser_ieee._ieee_url(
        "Exact Paper", 1, exact_title=True
    )
