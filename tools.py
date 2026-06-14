"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    # Step 1: load all listings
    listings = load_listings()

    # Step 2: filter by price and size
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    if size is not None:
        size_lower = size.lower()
        def _size_matches(listing_size: str) -> bool:
            # Tokenize on /, space, parens so "L" doesn't match "XL"
            tokens = re.split(r"[\s/()\-]+", listing_size.lower())
            return size_lower in tokens
        listings = [l for l in listings if _size_matches(l["size"])]

    # Step 3: score each listing by keyword overlap with description
    keywords = description.lower().split()

    def _score(listing: dict) -> int:
        text = " ".join([
            listing["title"],
            listing["description"],
            listing["category"],
            " ".join(listing["style_tags"]),
            " ".join(listing["colors"]),
            listing.get("brand") or "",
        ]).lower()
        return sum(1 for kw in keywords if kw in text)

    scored = [(_score(l), l) for l in listings]

    # Step 4: drop zero-score listings
    scored = [(s, l) for s, l in scored if s > 0]

    # Step 5: sort by score descending and return
    scored.sort(key=lambda x: x[0], reverse=True)
    return [l for _, l in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    if not new_item or not isinstance(new_item, dict):
        return (
            "Error: no valid item selected. Please retry the search to find "
            "a listing before requesting an outfit suggestion."
        )

    client = _get_groq_client()

    item_summary = (
        f"Name: {new_item.get('title', 'Unknown')}\n"
        f"Category: {new_item.get('category', '')}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Description: {new_item.get('description', '')}"
    )

    # Step 1: check if wardrobe is empty
    wardrobe_items = wardrobe.get("items") or []

    # Step 2: empty wardrobe — give general styling advice without crashing
    if not wardrobe_items:
        prompt = (
            "You are a fashion stylist who specializes in thrifted and vintage clothing.\n\n"
            "A user is considering buying this item:\n"
            f"{item_summary}\n\n"
            "They haven't shared their wardrobe yet. Give them general styling advice: "
            "what types of pieces pair well with this item, what aesthetic it fits, "
            "and 1–2 complete outfit ideas built around common wardrobe staples. "
            "Be specific and casual — 3–4 sentences."
        )
    else:
        # Step 3: wardrobe provided — suggest specific combinations using named pieces
        wardrobe_lines = "\n".join(
            f"- {item['name']} ({item['category']}) "
            f"colors: {', '.join(item.get('colors', []))}; "
            f"style: {', '.join(item.get('style_tags', []))}"
            for item in wardrobe_items
        )
        prompt = (
            "You are a fashion stylist who specializes in thrifted and vintage clothing.\n\n"
            "A user is considering buying this item:\n"
            f"{item_summary}\n\n"
            "Here is their current wardrobe:\n"
            f"{wardrobe_lines}\n\n"
            "Suggest 1–2 complete outfit combinations pairing the new item with specific "
            "named pieces from their wardrobe. Explain briefly why each combination works "
            "(colors, vibe, style overlap). Be casual and specific — 3–5 sentences total."
        )

    # Step 4: call the LLM and return its response as a string
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Step 1: guard against empty or whitespace-only outfit
    if not outfit or not outfit.strip():
        return (
            "Error: outfit suggestion is missing or incomplete. "
            "Please retry the search or add wardrobe details before generating a fit card."
        )

    title    = new_item.get("title", "this thrifted find")
    price    = new_item.get("price", "")
    platform = new_item.get("platform", "")

    # Step 2: build the prompt
    prompt = (
        "You are writing a casual, authentic OOTD caption for Instagram or TikTok — "
        "the kind a real person would post, not a brand.\n\n"
        f"The thrifted item: {title}"
        + (f", ${price}" if price else "")
        + (f" from {platform}" if platform else "")
        + f"\n\nThe outfit: {outfit}\n\n"
        "Write a 2–4 sentence caption that:\n"
        "- Sounds like a real person, not a product description\n"
        "- Mentions the item name, price, and platform once each, naturally\n"
        "- Captures the specific vibe of the outfit (don't just say 'cute' or 'love it')\n"
        "- Could be posted as-is on social media\n"
        "Return only the caption — no intro, no label, no quotes."
    )

    # Step 3: call LLM at higher temperature so each run sounds different
    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.1,
    )
    return response.choices[0].message.content
