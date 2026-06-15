# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

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
Searches the mock listings dataset for items that match a natural language description, an optional size filter, and an optional price ceiling. Returns a ranked list of matching listings sorted by relevance score (highest first).

**Input parameters:**
- `description` (str): Keywords describing what the user wants (e.g. "vintage graphic tee"). Used to score each listing by keyword overlap against title, style_tags, and description fields.
- `size` (str | None): Size string to filter by, case-insensitive (e.g. "M" matches "S/M"). If None, no size filter is applied.
- `max_price` (float | None): Maximum price inclusive. If None, no price filter is applied.

**What it returns:**
A list of listing dicts sorted by relevance score, highest first. Each dict contains: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str). Returns an empty list if nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to a specific message: "No listings found for '[query]'. Try a broader description, a different size, or a higher price limit." The agent returns the session immediately — it does not call `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted listing the user is considering and their existing wardrobe, calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfit combinations using the new item and named pieces from the wardrobe.

**Input parameters:**
- `new_item` (dict): A listing dict (the selected top result from `search_listings`). The LLM prompt includes the item's title, category, colors, style_tags, and condition.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts (each with name, category, colors, style_tags, notes). May have an empty `items` list.

**What it returns:**
A non-empty string with 1–2 outfit suggestions. Each suggestion names specific wardrobe pieces and describes the vibe. If the wardrobe is empty, returns general styling advice for the new item instead (e.g. what types of bottoms or shoes would complement it).

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the LLM is still called with a prompt for general styling ideas — the function never raises an exception or returns an empty string. If the LLM call fails, return a fallback string: "Could not generate outfit suggestion. Please try again."

---

### Tool 3: create_fit_card

**What it does:**
Calls the Groq LLM to generate a 2–4 sentence casual, shareable caption (Instagram/TikTok OOTD style) for the thrifted find and its suggested outfit. Uses a higher temperature (0.9) so output varies across runs.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`. Must be non-empty — guarded before the LLM call.
- `new_item` (dict): The listing dict for the thrifted item. Used to include the item name, price, and platform naturally in the caption.

**What it returns:**
A 2–4 sentence string that mentions the item name, price, and platform once each; captures the outfit vibe in specific terms; and sounds like a real person's OOTD post, not a product description.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, return the error string: "Cannot generate a fit card without an outfit suggestion." — do not call the LLM or raise an exception.

---

### Additional Tools (if any)

None beyond the three required tools.

---

## Planning Loop

The agent follows a strict linear sequence with one conditional branch:

1. **Parse the query** using regex to extract `description` (everything that isn't a size or price token), `size` (matches patterns like "size M", "in M", "sz M"), and `max_price` (matches patterns like "under $30", "$30", "30 dollars"). Store in `session["parsed"]`.

2. **Call `search_listings`** with the parsed parameters. Store results in `session["search_results"]`.
   - **If results is empty:** set `session["error"] = "No listings found for '<description>'. Try a broader description, a different size, or a higher price limit."` and return the session immediately. Do NOT proceed.
   - **If results is non-empty:** set `session["selected_item"] = results[0]` (top-ranked item) and continue.

3. **Call `suggest_outfit`** with `session["selected_item"]` and `session["wardrobe"]`. Store the returned string in `session["outfit_suggestion"]`.

4. **Call `create_fit_card`** with `session["outfit_suggestion"]` and `session["selected_item"]`. Store the returned string in `session["fit_card"]`.

5. **Return the session.** The agent is done.

The agent never retries failed tools or loops back. Each tool is called at most once per interaction.

---

## State Management

All state lives in a single session dict initialized by `_new_session()`:

| Key | Type | Set by | Consumed by |
|-----|------|--------|-------------|
| `query` | str | initialization | query parser |
| `parsed` | dict (`description`, `size`, `max_price`) | query parser | `search_listings` |
| `search_results` | list[dict] | `search_listings` | planning loop branch |
| `selected_item` | dict or None | planning loop (results[0]) | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | dict | initialization (caller) | `suggest_outfit` |
| `outfit_suggestion` | str or None | `suggest_outfit` | `create_fit_card` |
| `fit_card` | str or None | `create_fit_card` | returned to caller |
| `error` | str or None | planning loop on early exit | returned to caller |

No global state. Each call to `run_agent()` creates a fresh session dict — no state persists between interactions.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Sets `session["error"]` to: "No listings found for '[description]'. Try a broader description, a different size, or a higher price limit." Returns session immediately — outfit and fit card remain None. |
| suggest_outfit | Wardrobe is empty (`wardrobe["items"] == []`) | Calls the LLM with a general styling prompt instead of a wardrobe-specific one. Returns a non-empty string like "This item pairs well with high-waisted wide-leg trousers and chunky sneakers for a 90s streetwear vibe." |
| create_fit_card | Outfit input is empty or whitespace-only | Returns the string: "Cannot generate a fit card without an outfit suggestion." No LLM call is made. |

---

## Architecture

```
User query (natural language)
    │
    ▼
Planning Loop
    │
    ├─ Step 1: Parse query (regex)
    │       └─► session["parsed"] = {description, size, max_price}
    │
    ├─ Step 2: search_listings(description, size, max_price)
    │       │
    │       ├─► results == []
    │       │       └─► session["error"] = "No listings found..."
    │       │           return session  ◄─── EARLY EXIT
    │       │
    │       └─► results = [item, ...]
    │               └─► session["search_results"] = results
    │                   session["selected_item"]  = results[0]
    │
    ├─ Step 3: suggest_outfit(selected_item, wardrobe)
    │       │
    │       ├─► wardrobe["items"] == []
    │       │       └─► LLM prompt: general styling advice (no wardrobe)
    │       │
    │       └─► wardrobe["items"] != []
    │               └─► LLM prompt: specific outfit using named wardrobe pieces
    │
    │           session["outfit_suggestion"] = LLM response
    │
    └─ Step 4: create_fit_card(outfit_suggestion, selected_item)
            │
            ├─► outfit is empty/whitespace
            │       └─► return "Cannot generate a fit card without an outfit suggestion."
            │
            └─► LLM prompt: casual OOTD caption (temp=0.9)
                    session["fit_card"] = LLM response
                    return session  ◄─── NORMAL EXIT
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

- **`search_listings`**: Give Claude the Tool 1 spec block (inputs, return value, failure mode, scoring logic) and the weighted scoring algorithm (title=3, style_tags=2, description=1). Ask it to implement the function using `load_listings()` from the data loader. Before running: verify the generated code filters by both `max_price` and `size` (case-insensitive substring match), scores with the correct weights, drops zero-score listings, and returns an empty list (not an exception) when nothing matches. Test with 3 queries: "vintage graphic tee" (expect results), "designer ballgown size XXS under $5" (expect empty list), "jacket under $10" (verify all returned items price ≤ 10).

- **`suggest_outfit`**: Give Claude the Tool 2 spec block (inputs, return value, both branches — empty vs. non-empty wardrobe). Ask it to implement using Groq `llama-3.3-70b-versatile`. Before running: confirm the empty-wardrobe branch exists and calls the LLM with a general styling prompt, and the non-empty branch formats wardrobe items by name. Test with `get_example_wardrobe()` and `get_empty_wardrobe()` — both must return a non-empty string.

- **`create_fit_card`**: Give Claude the Tool 3 spec block (inputs, return value, empty-outfit guard, caption style guidelines, temperature=0.9). Before running: confirm the empty-string guard is the first check and returns without calling the LLM. Run 3 times on the same input and verify outputs differ (temperature working).

**Milestone 4 — Planning loop and state management:**

Give Claude the full Architecture diagram and both the Planning Loop and State Management sections. Ask it to implement `run_agent()` in `agent.py` following the exact numbered steps. Before using: verify the generated code (1) branches on empty results rather than calling all three tools unconditionally, (2) stores values in the session dict between steps, and (3) returns the session early if `search_results` is empty.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query with regex: `description = "vintage graphic tee"`, `size = None`, `max_price = 30.0`. It calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. The function loads all listings, filters to those priced ≤ $30, scores each by keyword overlap (e.g. lst_006 "Graphic Tee — 2003 Tour Bootleg Style" scores high on "graphic tee" in title and style_tags), and returns a ranked list. Top result: lst_006 — "Graphic Tee — 2003 Tour Bootleg Style, $24, depop, good condition." This is stored as `session["selected_item"]`.

**Step 2:**
The agent calls `suggest_outfit(session["selected_item"], session["wardrobe"])`. The wardrobe (example wardrobe) has 10 items. The LLM receives a prompt describing the band tee (black, graphic, slightly boxy, streetwear/grunge tags) and the wardrobe items. It returns something like: "Pair this with your baggy straight-leg dark wash jeans and chunky white sneakers for a classic 90s streetwear look. Add the black cropped zip hoodie over the top for extra edge on cooler days." Stored as `session["outfit_suggestion"]`.

**Step 3:**
The agent calls `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. The LLM receives the outfit suggestion and item details, and generates a casual caption at temperature 0.9. Example output: "thrifted this faded graphic tee off depop for $24 and it immediately became the center of every outfit 🖤 styled it with my baggy dark wash jeans and chunky sneakers — full 90s no notes." Stored as `session["fit_card"]`.

**Final output to user:**
Three panels populate in the Gradio UI:
- **Top listing found:** "Graphic Tee — 2003 Tour Bootleg Style | $24.00 | depop | Size: L | Condition: good | Tags: graphic tee, vintage, grunge, streetwear, band tee"
- **Outfit idea:** The suggest_outfit string (specific outfit combos using named wardrobe pieces)
- **Your fit card:** The create_fit_card caption (casual, shareable, OOTD style)

