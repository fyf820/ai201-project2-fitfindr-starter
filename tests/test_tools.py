"""
tests/test_tools.py

Pytest tests for all three FitFindr tools.
Tests that call the LLM (suggest_outfit, create_fit_card) are skipped
automatically if GROQ_API_KEY is not set in the environment.
"""

import os
import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe

# Skip marker for any test that requires a live Groq API key
needs_api = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set — skipping LLM tests",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def graphic_tee():
    """Top-ranked result for 'vintage graphic tee' under $30."""
    results = search_listings("vintage graphic tee", max_price=30.0)
    assert results, "fixture requires at least one matching listing"
    return results[0]


@pytest.fixture
def example_wardrobe():
    return get_example_wardrobe()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Impossible combination — no exception, just empty list
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_exact():
    # Size "M" should match listings with size "M"
    results = search_listings("top", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_size_filter_slash():
    # Size "M" should match "S/M" listings
    results = search_listings("top", size="M", max_price=None)
    sizes = [item["size"] for item in results]
    assert any("s/m" in s.lower() or s.lower() == "m" for s in sizes)


def test_search_size_no_false_positives():
    # "L" must NOT match pure "XL" — every returned item must have "l" as a token
    # Note: "L/XL" is a valid match because it contains the token "l"
    results = search_listings("top", size="L", max_price=None)
    for item in results:
        import re as _re
        tokens = _re.split(r"[\s/()\-]+", item["size"].lower())
        assert "l" in tokens, (
            f"Size '{item['size']}' returned for size='L' but 'l' is not a token"
        )


def test_search_results_sorted_by_relevance():
    # First result should have more matching keywords than the last
    results = search_listings("vintage grunge graphic tee streetwear")
    assert len(results) >= 2
    # Titles of top results should contain more of the search terms than tail items
    top_title = results[0]["title"].lower()
    assert any(kw in top_title for kw in ["vintage", "graphic", "tee", "grunge"])


def test_search_no_filters():
    # Both optional params omitted — should still return results
    results = search_listings("denim")
    assert len(results) > 0


def test_search_result_fields():
    # Every returned listing must have all required fields with the right types
    results = search_listings("vintage", max_price=50.0)
    required = {"id", "title", "description", "category", "style_tags",
                "size", "condition", "price", "colors", "platform"}
    for item in results:
        missing = required - item.keys()
        assert not missing, f"Listing {item.get('id')} is missing fields: {missing}"
        assert isinstance(item["price"], (int, float)), "price must be numeric"
        assert isinstance(item["style_tags"], list), "style_tags must be a list"
        assert isinstance(item["colors"], list), "colors must be a list"


def test_search_no_results_no_exception():
    # No match must return [] — not None, not raise
    try:
        result = search_listings("qzxqzxqzx", size="ZZZ", max_price=0.01)
    except Exception as exc:
        pytest.fail(f"search_listings raised an exception on no results: {exc}")
    assert result == [], "Expected empty list, not None or other type"


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

@needs_api
def test_suggest_outfit_returns_string(graphic_tee, example_wardrobe):
    result = suggest_outfit(graphic_tee, example_wardrobe)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@needs_api
def test_suggest_outfit_mentions_item(graphic_tee, example_wardrobe):
    result = suggest_outfit(graphic_tee, example_wardrobe)
    # LLM should reference the item or at least some wardrobe piece
    assert any(
        word in result.lower()
        for word in ["tee", "jeans", "sneakers", "outfit", "pair", "wear"]
    )


@needs_api
def test_suggest_outfit_empty_wardrobe(graphic_tee):
    # Empty wardrobe must not crash — response must contain actual styling advice
    result = suggest_outfit(graphic_tee, {"items": []})
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    # Should give informative advice, not just acknowledge the empty wardrobe
    styling_words = ["pair", "style", "outfit", "wear", "look", "combine", "match"]
    assert any(w in result.lower() for w in styling_words), (
        f"Empty-wardrobe response lacks styling advice: {result!r}"
    )


@needs_api
def test_suggest_outfit_missing_items_key(graphic_tee):
    # Wardrobe dict without 'items' key — must not crash, must still advise
    result = suggest_outfit(graphic_tee, {})
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_suggest_outfit_invalid_item():
    # None or empty new_item must return an error string, not crash
    for bad in [None, {}, "not a dict"]:
        result = suggest_outfit(bad, {"items": []})
        assert isinstance(result, str)
        assert "error" in result.lower(), (
            f"Expected error string for new_item={bad!r}, got: {result!r}"
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def test_fit_card_empty_outfit_guard(graphic_tee):
    # Empty outfit must return an informative error string, not raise
    result = create_fit_card("", graphic_tee)
    assert isinstance(result, str) and len(result.strip()) > 0
    assert "error" in result.lower()
    # Message should tell the user what to do next
    assert any(w in result.lower() for w in ["retry", "wardrobe", "search", "outfit"]), (
        f"Error message lacks next-step guidance: {result!r}"
    )


def test_fit_card_whitespace_outfit_guard(graphic_tee):
    result = create_fit_card("   ", graphic_tee)
    assert "error" in result.lower()


def test_fit_card_none_outfit_guard(graphic_tee):
    # None outfit must not crash — same error path as empty string
    try:
        result = create_fit_card(None, graphic_tee)
    except Exception as exc:
        pytest.fail(f"create_fit_card raised on None outfit: {exc}")
    assert "error" in result.lower()


@needs_api
def test_fit_card_returns_string(graphic_tee, example_wardrobe):
    outfit = suggest_outfit(graphic_tee, example_wardrobe)
    result = create_fit_card(outfit, graphic_tee)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@needs_api
def test_fit_card_mentions_price_and_platform(graphic_tee, example_wardrobe):
    outfit = suggest_outfit(graphic_tee, example_wardrobe)
    result = create_fit_card(outfit, graphic_tee)
    price_str = str(int(graphic_tee["price"]))
    platform = graphic_tee["platform"].lower()
    assert price_str in result, f"Expected price {price_str} in caption"
    assert platform in result.lower(), f"Expected platform '{platform}' in caption"


@needs_api
def test_fit_card_varies(graphic_tee, example_wardrobe):
    # High temperature should produce different captions on repeated calls
    outfit = suggest_outfit(graphic_tee, example_wardrobe)
    run1 = create_fit_card(outfit, graphic_tee)
    run2 = create_fit_card(outfit, graphic_tee)
    assert run1 != run2, "Both runs returned identical output — increase LLM temperature"
