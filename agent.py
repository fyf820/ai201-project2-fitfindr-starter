"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "retry_attempted": False,    # True after the first broadened retry
        "retry_note": None,          # human-readable note about what filter was dropped
        "wardrobe_empty": False,     # True when user submitted no wardrobe items
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a lowercased natural language query.
    Uses regex — no LLM call needed for this structured extraction.
    """
    query = query.lower()

    # max_price: "under $30", "under 30", "$30", "below $40", "less than $25"
    price_m = re.search(
        r'(?:under|below|max(?:imum)?|less\s+than)\s*\$?(\d+(?:\.\d+)?)', query
    )
    if not price_m:
        price_m = re.search(r'\$(\d+(?:\.\d+)?)', query)
    max_price = float(price_m.group(1)) if price_m else None

    # size: "size M", "in size XL", "size s/m"
    size_m = re.search(r'\b(?:in\s+)?size\s+([a-z0-9]+(?:/[a-z0-9]+)?)\b', query)
    size = size_m.group(1).upper() if size_m else None

    # description: strip price, size, and common opener phrases
    desc = query
    for pattern in [
        r'(?:under|below|max(?:imum)?|less\s+than)\s*\$?\d+(?:\.\d+)?',
        r'\$\d+(?:\.\d+)?',
        r'\b(?:in\s+)?size\s+[a-z0-9]+(?:/[a-z0-9]+)?\b',
        r"^(?:i'?m\s+)?(?:looking for|searching for|find me|i want|show me|need)\s+(?:an?\s+)?",
    ]:
        desc = re.sub(pattern, ' ', desc)
    desc = re.sub(r'\s+', ' ', desc).strip(' ,.')

    return {
        "description": desc if desc else query,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: initialize session
    session = _new_session(query, wardrobe)

    # Step 2: parse query into description / size / max_price
    parsed = _parse_query(query)
    session["parsed"] = parsed
    description = parsed["description"]
    size        = parsed["size"]
    max_price   = parsed["max_price"]

    # Step 3: first search attempt
    results = search_listings(description, size=size, max_price=max_price)

    # Retry once with loosened constraints (planning.md error-handling spec)
    if not results:
        session["retry_attempted"] = True
        if size is not None:
            results = search_listings(description, size=None, max_price=max_price)
            session["retry_note"] = f"No results for size '{size}' — automatically retried without size filter."
        elif max_price is not None:
            results = search_listings(description, size=None, max_price=None)
            session["retry_note"] = f"No results under ${max_price:.0f} — automatically retried without price limit."

    session["search_results"] = results

    if not results:
        session["error"] = (
            f"No listings found for '{description}'"
            + (f", size {size}" if size else "")
            + (f", under ${max_price:.0f}" if max_price else "")
            + ". Try different keywords, a wider size, or a higher budget."
        )
        return session

    # Step 4: select top result
    session["selected_item"] = results[0]

    # Step 5: suggest outfit
    session["wardrobe_empty"] = not bool(wardrobe.get("items") or [])
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], wardrobe
    )

    # Step 6: create fit card (passes clean outfit string — nudge added by app.py)
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
