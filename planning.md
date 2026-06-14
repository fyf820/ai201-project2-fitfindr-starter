# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

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
         ├─ wardrobe empty → returns general styling advice
         │    │
         │    └─► agent appends nudge to outfit_suggestion:
         │         "Switch to Example wardrobe for named-piece combos"
         │
         └─ outfit = str (styling suggestion with named wardrobe pieces)
              │
              ├─ Session: outfit_suggestion = outfit
              │
              ▼
         create_fit_card(outfit=outfit_suggestion, new_item=selected_item)
              │
              ├─ outfit empty/None → returns error string
              │    │
              │    └─► error shown in fit card panel
              │         (user prompted to retry or add wardrobe details)
              │
              └─ fit_card = str (OOTD caption)
                   │
                   ├─ Session: fit_card = fit_card
                   │
                   ▼
              ┌──────────────────────────┐
              │  Return to User:         │
              │  - selected_item details │
              │  - outfit_suggestion     │
              │  - fit_card              │
              └──────────────────────────┘

════════════════════════════════════════════════════════════════════════════
                          SESSION STATE (persistent across tools)
                          - query, parsed, search_results, retry_attempted
                          - selected_item, wardrobe, outfit_suggestion
                          - fit_card, error
════════════════════════════════════════════════════════════════════════════
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I 'll give Claude the Tool 1 spec (inputs, return value, failure mode) from planning.md plus `load_listings()` from data_loader.py, and asked it to implement `search_listings` in tools.py. I verify it by running three test queries (matching results, no results, price-filtered) and checked that empty inputs returned `[]` without crashing. I repeated this process for Tool 2 using the Tool 2 spec and wardrobe_schema.json, and for Tool 3 using the Tool 3 spec and running `create_fit_card("", item)` and `create_fit_card(None, item)` to confirm the guard worked before accepting the output.

**Milestone 4 — Planning loop and state management:**
I'll give Claude the Planning Loop and State Management sections of planning.md and asked it to implement `run_agent` step by step. I verify it by running the CLI test in agent.py against both the happy path ("vintage graphic tee under $30") and the no-results path ("designer ballgown size XXS under $5"), confirming that `session["fit_card"]` was `None` and `suggest_outfit` was never called on the error path (verified with a mock spy).

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
Call the search_listings tool("vintage graphic tee", , max_price=30.0), returns 3 matching listings, FitFindr picks the top result

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
Call suggest_outfit(new_item=<band tee>, wardrobe=<user's wardrobe>) returns a suggeted outfit
**Step 3:**
<!-- Continue until the full interaction is complete -->
Call create_fit_card(outfit=<suggestion>, new_item=<band tee>) returns a description of a complete outfit
**Final output to user:**
<!-- What does the user actually see at the end? -->
A readble card description of a complete outfit returned in step 3