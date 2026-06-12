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
Search the data in listings and return the results. Can handle missing inputs like no size or max_price. Will retry with loosend constrains once if no results.
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
If there are some errors, the agent will show the error to the user and ask the user to change the input to try again. 
If the first search returns no results:
   - Automatically retry once with loosened constraints.
   - The retry should broaden filters by dropping or widening `size`, relaxing `max_price`, or loosening keywords.
If retry still returns no results:
   - Ask the user for more item details.
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
A dict containing:
new_item: the first item search_listings returned
selected_items: list[dict] of wardrobe pieces used in the outfit
styling_notes: str explanation of why the pieces work together
outfit_type: str label such as casual, grunge, or streetwear
**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If the wardrobe is empty or no outfit can be suggested,  it returns an empty suggestion and the agent asks the user for more wardrobe details or offers to use the example wardrobe.
---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Create a short, shareable fit description of the completed outfit. Mentions the new item, styling details, and why the look works.
**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (dict): suggestion returned by suggest_outfit
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
7. If `suggest_outfit` fails or returns no valid outfit:
   - Ask the user to add more wardrobe details or offer the example wardrobe.
   - Retry `suggest_outfit` once the wardrobe improves.
8. If outfit suggestion succeeds:
   - Call `create_fit_card(outfit=suggested_outfit, new_item=top_match)`.
9. Return the final fit description of a complete outfitto the user.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
The agent maintains a session state object with the following fields:
- `query`: the original user request
- `search_description`, `search_size`, `search_max_price`: parsed search parameters
- `search_results`: list returned by `search_listings`
- `retry_attempted`: boolean flag tracking whether the first search was already retried
- `selected_item`: the top match chosen from `search_results`
- `wardrobe`: the user's wardrobe object (either user-provided or example)
- `suggested_outfit`: result from `suggest_outfit`
- `fit_card`: final output from `create_fit_card`

**Data flow between tools:**
- `search_listings` returns a list; the agent selects the top item and stores it as `selected_item`.
- `selected_item` is passed as `new_item` to `suggest_outfit` along with the `wardrobe` object.
- `suggested_outfit` is passed to `create_fit_card` along with `selected_item` (the `new_item`).
- If `search_listings` fails after retry, the session state marks `retry_attempted=True` and `search_results=[]`, and the agent asks the user for a revised query before continuing.

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
         ├─ outfit = {} (empty wardrobe or no match)
         │    │
         │    └─► [ERROR] Ask user for more wardrobe details ─────┐
         │         │                                              │
         │         └─ [RETRY] suggest_outfit with new wardrobe ◄─┘
         │
         └─ outfit = {selected_items, styling_notes, outfit_type}
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
I'll use the Claude and gives the tools spec in planning, ask it to implement all three methods. I will also give tools in data_loader and ask it complete tools one by one. I will check and test it until complete all three tools.

**Milestone 4 — Planning loop and state management:**
I'll ask the Claude to and gives the planning loop and state management specs in planning, ask it to complete it. I will ask it to complete step by step based on the planning loop and test each step until it complete it.

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