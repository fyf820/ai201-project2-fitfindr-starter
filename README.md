# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.


### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Search the data in listings and return the results. Can handle missing inputs like no size or max_price. Returns an empty list if nothing matches — the planning loop owns the retry logic.
**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): user style description or search keywords
- `size` (str): size of the item
- `max_price` (float): max price of the item

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A list of dict of items searched from listings includes:
id, title, price, size, category, style_tags, colors, brand, platform, description


**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
The tool always returns a list and never raises an exception. If nothing matches, it returns `[]`. The planning loop in `run_agent` detects the empty list and retries once with loosened constraints (drops `size` first, then `max_price`). If the retry also returns `[]`, the agent sets `session["error"]` and stops before calling `suggest_outfit`.
---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Generate outfit suggestions by pairing the selected listing with one or more pieces from the user’s wardrobe. Uses category, color, and style tags to create a complete outfit combinations.
**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): the first item search_listings returned
- `wardrobe` (dict): the user’s wardrobe object with items in the schema format

**What it returns:**
<!-- Describe the return value -->
A string containing 1–2 complete outfit suggestions, naming specific wardrobe pieces and explaining why each combination works. If the wardrobe is empty, returns general styling advice instead.
**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If the wardrobe is empty or no outfit can be suggested,  it returns a common suggestion and the agent asks the user for more wardrobe details or offers to use the example wardrobe.
---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Create a short, shareable fit description of the completed outfit. Mentions the new item, styling details, and why the look works.
**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): suggestion string returned by suggest_outfit
- `new_item` (dict): the first item search_listings returned

**What it returns:**
<!-- Describe the return value -->
A string that describes a complete outfit

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If required input is missing or the outfit is incomplete, it returns an explicit error response.
The agent then tells the user it cannot create a fit card yet and asks whether to retry the search or provide more wardrobe details.
---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
1. Parse the user query into `description`, `size`, `max_price`, and wardrobe clues.
2. Call `search_listings(description, size, max_price)`.
3. If the first search returns no results:
   - Automatically retry once with loosened constraints.
   - The retry should broaden filters by dropping or widening `size`, relaxing `max_price`, or loosening keywords.
4. If retry still returns no results:
   - Ask the user for more item details.
   - Do not call `suggest_outfit` until the user provides a better search query.
5. If search results exist:
   - Select the top match as `top_match`.
   - Store `search_results` and `selected_item` in session state.
6. Call `suggest_outfit(new_item=top_match, wardrobe=user_wardrobe)`.
7. If the wardrobe was empty, `suggest_outfit` returns general styling advice. The agent appends a note to `outfit_suggestion` telling the user to switch to "Example wardrobe" for personalised combinations. (Gradio is single-request, so the nudge is embedded in the output rather than an interactive re-prompt.)
8. Call `create_fit_card(outfit=outfit_suggestion, new_item=top_match)`. If `outfit_suggestion` is empty or missing, `create_fit_card` returns an error string — surfaced in the fit card panel without crashing.
9. Return the completed session to the user.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
The agent maintains a session state object with the following fields:
- `query`: the original user request
- `parsed`: dict containing `description`, `size`, and `max_price` extracted from the query
- `search_results`: list returned by `search_listings`
- `retry_attempted`: boolean flag tracking whether the first search was already retried
- `retry_note`: human-readable message explaining which filter was dropped on retry (e.g. "No results for size 'XXXL' — automatically retried without size filter"), or `None` if no retry occurred
- `selected_item`: the top match chosen from `search_results`
- `wardrobe`: the user's wardrobe object (either user-provided or example)
- `outfit_suggestion`: string result from `suggest_outfit`
- `fit_card`: string result from `create_fit_card`
- `error`: set to a message string if the interaction ended early, otherwise `None`

**Data flow between tools:**
- `search_listings` returns a list; the agent selects the top item and stores it as `selected_item`.
- `selected_item` is passed as `new_item` to `suggest_outfit` along with the `wardrobe` object.
- `outfit_suggestion` is passed to `create_fit_card` along with `selected_item` (the `new_item`).
- If `search_listings` returns `[]` after retry, the agent sets `session["error"]` and returns early without calling `suggest_outfit`.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | First search returns no results |Automatically retry once with boarden filter |
| search_listings | Second search returns no results |Ask the user for more item details and stop before calling suggest_outfit|
| suggest_outfit | Wardrobe is empty |ask for more wardrobe info or offer to use example wardrobe|
| suggest_outfit | new_item is missing or invalid |ask the user to retry the search with a valid item|
| create_fit_card | Outfit input is missing or incomplete |Tell the user the fit card cannot be generated yet and ask to complete the outfit suggestion|

---

## Error Handling Strategy

**search_listings** — if the first search returns no results, the agent retries once with loosened constraints: it drops the size filter first, or removes the price ceiling if no size was given. If results are still empty, `session["error"]` is set and the agent returns early without calling `suggest_outfit`.

*Example from testing:* query `"designer ballgown size XXS under $5"` — first search found nothing. Retry dropped size XXS and searched again; still nothing under $5. Result: `session["error"] = "No listings found for 'designer ballgown', size XXS, under $5. Try different keywords, a wider size, or a higher budget."`, `session["fit_card"] = None`, and `suggest_outfit` was never called (verified with a mock spy in tests).

**suggest_outfit** — if `wardrobe["items"]` is empty or missing, the tool does not crash. It switches to a general styling prompt asking the LLM for outfit ideas around common wardrobe staples instead of named wardrobe pieces.

*Example from testing:* calling `suggest_outfit(item, {"items": []})` returned a full styling paragraph containing words like "pair", "style", and "outfit" — not an empty string or exception.

**create_fit_card** — if `outfit` is empty, whitespace-only, or `None`, the tool returns an error string immediately without calling the LLM.

*Example from testing:* `create_fit_card("", item)` and `create_fit_card(None, item)` both returned `"Error: outfit suggestion is missing or incomplete. Please retry the search or add wardrobe details before generating a fit card."` — no exception in either case.

---

## Architecture

```
User Input (query + wardrobe hints)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PLANNING LOOP                                     │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
search_listings(description, size, max_price)
    │
    ├─ results = [] (first attempt)
    │    │
    │    ├─► [RETRY] Broaden filters (drop size, relax price, widen keywords)
    │    │    │
    │    │    └─► results still = []
    │    │         │
    │    │         └─► [ERROR] Ask user for more item details ──────┐
    │    │                                                           │
    │    └─ results = [] (after retry) ───────────────────────────────┤
    │                                                                 │
    └─ results = [item1, item2, ...] ◄─ User provides revised query ◄┘
         │
         ├─ Session: selected_item = results[0]
         ├─ Session: search_results = results
         ├─ Session: retry_attempted = true
         │
         ▼
    suggest_outfit(new_item=selected_item, wardrobe=user_wardrobe)
         │
         ├─ outfit = {} (empty wardrobe or no match)
         │    │
         │    └─► [ERROR] Ask user for more wardrobe details ─────┐
         │         │                                              │
         │         └─ [RETRY] suggest_outfit with new wardrobe ◄─┘
         │
         └─ outfit = str (styling suggestion with named wardrobe pieces)
              │
              ├─ Session: suggested_outfit = outfit
              │
              ▼
         create_fit_card(outfit=suggested_outfit, new_item=selected_item)
              │
              ├─ fit_card = {} (incomplete input)
              │    │
              │    └─► [ERROR] Tell user outfit is incomplete ──────┐
              │         (ask to retry search or add wardrobe)       │
              │                                                     │
              └─ fit_card = {summary}
                   │
                   ├─ Session: fit_card = fit_card
                   │
                   ▼
              ┌──────────────────────────┐
              │  Return to User:         │
              │  - fit_card[summary]     │
              │  - selected_item details │
              └──────────────────────────┘

════════════════════════════════════════════════════════════════════════════
                          SESSION STATE (persistent across tools)
                          - query, search_results, retry_attempted
                          - selected_item, wardrobe, suggested_outfit
                          - fit_card
════════════════════════════════════════════════════════════════════════════
```

---

## Spec Reflection

**One way the spec helped:** The planning.md error handling table defined exactly which tool owns each failure mode and what the agent does next if the error occured. This made the retry logic in `run_agent` straightforward because the priority order was already decided before any code was written.

**One way implementation diverged from the spec:** 
Tool 1's description says "Will retry with loosened constraints once if no results" — implying the retry is inside the tool. But the retry actually lives in run_agent in the planning loop. The tool just returns []. I have fixed the this issue to make the planning aligns with the implementation.

---



- I gave Claude the Tool 1 spec from planning.md and listings.json, and it generated the `search_listings` function. In my original tool design, the tool would auto re-search with a broader filter if the first search failed. But later I found this conflicted with my agent loop design.  The retry logic belongs in agent, not inside the tool. So I moved the retry out of the tool and kept `search_listings` as a pure search function that always returns `[]` on no match.

- I gave Claude the Tool 2 spec from planning.md plus wardrobe_schema.json, and it generated `suggest_outfit`. The spec said to return a dict with `selected_items`, `styling_notes`, and `outfit_type`. Claude followed that structure. I overrode the return type to a plain string because `create_fit_card` only needs the text to write a caption.

- I gave Claude the Planning Loop and State Management sections of planning.md and asked it to implement `run_agent` in agent.py. The spec described an interactive re-prompt at step 7: if the wardrobe is empty, ask the user to add wardrobe details before continuing. Claude initially skipped that branch. I kept the intent but adapted the implementation. Since Gradio is single-request and can't pause for user input mid-run, I replaced the re-prompt with an embedded nudge appended to `outfit_suggestion`: "Switch to 'Example wardrobe' for outfit combinations with specific named pieces." The user sees it in the outfit panel and can resubmit with the example wardrobe selected.

## Video
https://drive.google.com/file/d/1jA2ulmxpBjotDxD9ccRgjYVPdaKCJ5yy/view?usp=sharing