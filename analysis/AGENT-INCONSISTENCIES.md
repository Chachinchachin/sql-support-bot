# Agent Inconsistencies & Potential Issues

### 1. Inconsistent tool richness
`check_for_songs` returns all 9 Track columns, but `get_tracks_by_artist` returns only 2 (song name + artist name).

**Impact:** The agent's ability to answer follow-up questions depends on *which tool it happened to call first*. If a user asks "what songs does AC/DC have?" then follows up with "how long is the first one?", the agent has no duration data from the artist tool. It must either re-query using `check_for_songs` per track (inefficient, may not occur to the LLM) or hallucinate a duration. Two users asking the same question via slightly different phrasing could get wildly different quality answers.

### 2. Unresolved foreign keys
`check_for_songs` returns `GenreId = 1` and `MediaTypeId = 1` instead of "Rock" and "MPEG audio file".

**Impact:** The LLM receives a raw integer and must decide what to do with it. It might hallucinate "Genre 1 is Rock" (correct by coincidence from training data), say "the genre ID is 1" (useless to the user), or confidently map it wrong. This creates **non-deterministic correctness** — the same query might get the right genre name on one run and a wrong one on the next, with no way to verify. A user asking "do you have any jazz songs?" could get completely wrong recommendations.

### 3. No purchase history despite data existing
Invoice (412 rows) and InvoiceLine (2,240 rows) tables exist but no tool queries them.

**Impact:** A customer asking "what have I bought before?" or "can you help me with my recent order?" gets a dead end — the bot either says it can't help (bad experience for a *support* bot) or hallucinates purchase history. Worse, the system prompt says "help customers access their account information," implying order history should be available. This is a **broken user expectation** set by the bot's own framing.

### 4. Customer lookup requires ID, not name
`get_customer_info` takes `customer_id: int` only.

**Impact:** The ideal flow — user says "I'm Leonie Köhler, can you look up my account?" — immediately breaks. The bot must ask for a numeric ID that customers don't typically know. This adds friction and makes the bot feel robotic. A clever LLM might try to use `check_for_songs` or other tools to fish for the customer (they won't work), wasting tokens and time. In the worst case, it hallucinates a customer ID and returns the wrong person's data.

### 5. No album-to-tracks connection
`get_albums_by_artist` returns album titles, `get_tracks_by_artist` returns track names — but neither maps tracks to their specific album.

**Impact:** "What songs are on the album 'For Those About To Rock'?" requires connecting Album → Track, which no single tool does. The agent might call `get_tracks_by_artist("AC/DC")` and return *all* AC/DC songs across *all* albums — incorrect for the question asked. The user gets a sprawling list when they wanted a specific album's tracklist. There's also no tool to search by album name at all.

### 6. Milliseconds and bytes returned raw
`check_for_songs` returns `Milliseconds = 343719` and `Bytes = 11170334`.

**Impact:** The agent's answer quality becomes entirely dependent on the LLM's willingness to do math. gpt-4o at temperature=0 *usually* converts correctly, but a model swap (e.g., gpt-4o-mini for cost savings) might not. You could get "the song is 343719 milliseconds long" in production. This is **fragile presentation logic** — it works today by luck, not by design, and would break silently on model changes.

### 7. Full PII exposure with no access control
`get_customer_info` returns phone, fax, email, full address for any customer ID 1-59.

**Impact:** Any user can type "look up customer 42" and get a stranger's full personal information. There's no authentication or scoping. If this bot is customer-facing, this is a **data privacy violation**. Even if internal-facing, there's no audit trail. An attacker could enumerate all 59 customers in under a minute. The bot's system prompt doesn't instruct it to withhold sensitive fields, so it will happily read them all out.

### 8. Employee table is orphaned
Customer records have `SupportRepId` pointing to Employee, but no tool queries Employee.

**Impact:** A customer asking "who is my support rep?" gets a partial answer — the bot can return `SupportRepId = 3` from their account but can't resolve it to a name. The bot either presents a meaningless number, hallucinates a name, or says it doesn't know — all bad outcomes for a *support* bot. This also means the bot can't route escalations like "can I speak to my rep?" since it can't even identify who that person is.

### 9. SQL injection via f-string interpolation
All tools use f-strings: `WHERE Artist.Name LIKE '%{artist}%'`.

**Impact:** A user input containing a single quote (`'`) breaks the SQL query and causes an error — the bot crashes on a legitimate artist name like `"Sinead O'Connor"`. A `%` input matches every row, returning 3,503 tracks (potential token bomb that could hit context limits or cost money). While true SQL injection is limited by SQLite's read-only in-memory setup, the error-on-apostrophe issue means **real artist names will fail**, which is a straightforward bug.
