# FitFindr

FitFindr is an AI-powered thrift shopping assistant. Give it a natural language description of what you're looking for, and it finds a matching secondhand listing, suggests outfit combinations using your existing wardrobe, and generates a shareable OOTD caption — all in one interaction.

---

## How to Run

```bash
pip install -r requirements.txt
# Add your GROQ_API_KEY to a .env file in the project root
python app.py
```

Open the URL shown in your terminal (typically `http://localhost:7860`).

---

## Tool Inventory

### `search_listings(description, size, max_price)`

| Parameter | Type | Purpose |
|-----------|------|---------|
| `description` | `str` | Keywords describing the item (e.g. "vintage graphic tee") |
| `size` | `str \| None` | Size filter — case-insensitive substring match. `None` skips filtering. |
| `max_price` | `float \| None` | Maximum price inclusive. `None` skips filtering. |

**Returns:** `list[dict]` — matching listing dicts sorted by relevance score (highest first). Each dict has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches — never raises an exception.

**Purpose:** Filters and ranks the mock listings dataset against the user's query using weighted keyword overlap (title match = 3pts, style_tag match = 2pts, description match = 1pt).

---

### `suggest_outfit(new_item, wardrobe)`

| Parameter | Type | Purpose |
|-----------|------|---------|
| `new_item` | `dict` | A listing dict — the item the user is considering buying |
| `wardrobe` | `dict` | A wardrobe dict with an `items` key (list of wardrobe item dicts). May be empty. |

**Returns:** `str` — a non-empty string with 1–2 outfit suggestions. If the wardrobe is empty, returns general styling advice instead of wardrobe-specific combinations.

**Purpose:** Calls the Groq LLM (`llama-3.3-70b-versatile`, temperature 0.7) to suggest specific outfit combinations using the new item and named pieces from the user's wardrobe.

---

### `create_fit_card(outfit, new_item)`

| Parameter | Type | Purpose |
|-----------|------|---------|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit`. Must be non-empty. |
| `new_item` | `dict` | The listing dict for the thrifted item |

**Returns:** `str` — a 2–4 sentence casual OOTD caption mentioning the item name, price, and platform once each.

**Purpose:** Calls the Groq LLM (`llama-3.3-70b-versatile`, temperature 0.9) to generate a shareable Instagram/TikTok-style caption. Higher temperature ensures varied output across runs.

---

## Planning Loop

The agent follows a strict linear sequence with one conditional branch — it never retries or loops:

1. **Parse the query** using regex to extract `description`, `size`, and `max_price` from the user's natural language input.

2. **Call `search_listings`** with the parsed parameters.
   - If results is **empty**: set an error message in the session and return immediately. `suggest_outfit` and `create_fit_card` are never called.
   - If results is **non-empty**: store `results[0]` as `selected_item` and continue.

3. **Call `suggest_outfit`** with `selected_item` and the user's wardrobe. Store the returned string.

4. **Call `create_fit_card`** with the outfit suggestion and `selected_item`. Store the returned string.

5. **Return the session.** Done.

The key decision point is step 2: the agent's behavior differs fundamentally depending on whether `search_listings` returns results. If it does, all three tools run in sequence. If it doesn't, the agent stops immediately with a helpful error — it never calls `suggest_outfit` with empty input.

---

## State Management

All state lives in a single session dict created fresh for each interaction by `_new_session()`. No global state — nothing persists between calls to `run_agent()`.

| Key | Set by | Consumed by |
|-----|--------|-------------|
| `query` | initialization | query parser |
| `parsed` | query parser (regex) | `search_listings` |
| `search_results` | `search_listings` | planning loop branch check |
| `selected_item` | planning loop (`results[0]`) | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | initialization (caller) | `suggest_outfit` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | returned to UI |
| `error` | planning loop on early exit | returned to UI |

State passes between tools via this dict — `suggest_outfit` receives `session["selected_item"]` directly, and `create_fit_card` receives `session["outfit_suggestion"]` directly. No values are re-fetched or re-computed between steps.

---

## Error Handling

| Tool | Failure mode | Agent response | Tested example |
|------|-------------|----------------|----------------|
| `search_listings` | No listings match the query | Sets `session["error"]` to: `"No listings found for 'designer ballgown'. Try a broader description, a different size, or a higher price limit."` Returns session immediately — outfit and fit card remain `None`. | Query: `"designer ballgown size XXS under $5"` → `[]` returned, error shown in first UI panel, other panels empty. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"] == []`) | Calls the LLM with a general styling prompt instead of a wardrobe-specific one. Returns non-empty advice about what bottoms, shoes, and layers pair well with the item. | Called with `get_empty_wardrobe()` → returned: `"This graphic tee is perfect for a grunge-inspired, streetwear look. Pair with distressed denim jeans, chunky boots or Converse, and a denim or leather jacket."` |
| `create_fit_card` | Outfit string is empty or whitespace-only | Returns `"Cannot generate a fit card without an outfit suggestion."` immediately — no LLM call made, no exception raised. | Called with `create_fit_card("", item)` → returned error string instantly. |

---

## Spec Reflection

The implementation matched the planning spec closely with two minor deviations:

1. **`import re` placement** — in `agent.py`, `import re` was placed inside `run_agent()` rather than at the top of the file. This works correctly but is a style inconsistency with standard Python conventions. It has no effect on behavior.

2. **Filler word stripping in query parsing** — the spec described extracting a clean description by removing size/price tokens. The implementation also strips common filler phrases (`"looking for"`, `"i'm"`, `"i am"`, `"want"`, `"to buy"`) which wasn't explicitly in the spec but produces cleaner search terms. For example, `"looking for a vintage graphic tee under $30"` becomes `"vintage graphic tee"` rather than `"looking vintage tee"`.

Everything else — the three tools, the conditional branch logic, the session dict structure, the error strings, and the wardrobe empty-branch behavior — matched the spec exactly as written.

---

## AI Usage

### Instance 1 — Implementing `search_listings`

**Input given to Claude:** The Tool 1 spec block from `planning.md` (inputs with types, weighted scoring algorithm: title=3, style_tags=2, description=1, failure mode), plus the instruction to use `load_listings()` from the data loader.

**What it produced:** A complete implementation with correct price/size filtering, weighted scoring, zero-score filtering, and descending sort. Returned clean listing dicts by stripping the score before returning via `[listing for _, listing in results]`.

**What was verified before using:** Confirmed the size filter used case-insensitive substring matching (`size_filter not in listing["size"].lower()`), that zero-score listings were dropped with `if score == 0: continue`, and that the function returned `[]` (not an exception) on no match. Tested with 3 queries: broad match, impossible match, and price-bounded match — all passed.

### Instance 2 — Implementing `run_agent()` planning loop

**Input given to Claude:** The full Architecture ASCII diagram from `planning.md`, the Planning Loop section (5 numbered steps with conditional branch logic), and the State Management table.

**What it produced:** A complete `run_agent()` with regex query parsing (three price patterns, size pattern, filler word removal), the correct early-exit branch on empty `search_results`, and sequential tool calls storing results in the session dict at each step.

**What was changed before using:** The generated code had `import re` inside the function body rather than at the top of the file. This was left as-is since it functions correctly. The regex patterns for price parsing were reviewed against all 5 example queries in `app.py` and confirmed to handle each one before accepting the output.
