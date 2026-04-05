# Session Summary: SQL Support Bot Eval Planning

## Context
This repo is a take-home case study for a PM interview at LangSmith. The task: write evals for the SQL support bot agent, with a process to quickly assess performance after making changes. Time budget: ~4-8 hours.

## What the Agent Is
A customer support chatbot for a music store, built on the **Chinook SQLite database** (loaded in-memory). It uses **DeepAgents** with `gpt-4o` (temperature=0) for autonomous tool selection. Previously built with LangGraph (multi-node routing), it was recently simplified to a single-agent architecture.

It has **4 tools**:
- `get_albums_by_artist(artist)` — fuzzy search albums by artist name (returns 2 columns)
- `get_tracks_by_artist(artist)` — fuzzy search songs by artist name (returns 2 columns)
- `check_for_songs(song_title)` — search songs by title (returns all 9 Track columns)
- `get_customer_info(customer_id)` — lookup customer by numeric ID (returns all 13 Customer columns)

## Key Design Questions We Explored

### Who is this for?
Ambiguous. System prompt says "customer support chatbot" (customer-facing), but `get_customer_info` requires a numeric ID (suggests internal/support-agent-facing). This tension is itself an eval-worthy observation.

### What's the user journey?
Two journeys only: (1) music discovery via search, (2) account lookup by ID. Read-only — no purchases, no ticket creation, no escalation. Chat-only — no external APIs, webhooks, or integrations beyond OpenAI and the SQLite DB.

### What data is available vs. accessible?
The Chinook DB has **11 tables** but only **4 are queried** (Artist, Album, Track, Customer). Genre, MediaType, Invoice, InvoiceLine, Employee, Playlist, and PlaylistTrack are all present but untouched by any tool. See `analysis/SQL-TABLE-EXAMPLE.md` for full schema with sample rows.

## 9 Agent Inconsistencies Identified
See `analysis/AGENT-INCONSISTENCIES.md` for full details with impact analysis:

1. **Inconsistent tool richness** — `check_for_songs` returns 9 columns vs 2 for artist-based tools
2. **Unresolved foreign keys** — GenreId/MediaTypeId returned as raw integers
3. **No purchase history** — Invoice data exists but no tool queries it
4. **Customer lookup requires ID** — no name/email search, breaks natural user flow
5. **No album-to-tracks connection** — can't answer "what songs are on this album?"
6. **Raw milliseconds/bytes** — formatting depends on LLM math ability
7. **Full PII exposure** — no access control on customer data
8. **Orphaned employee table** — SupportRepId can't be resolved to a name
9. **SQL injection via f-strings** — apostrophes in artist names break queries

## Division of Labor: Human vs Claude

| Aspect | Owner | Rationale |
|---|---|---|
| Scenario brainstorming & prioritization | Human | PM judgment — interviewers want your thinking |
| Eval criteria / defining "good" | Human | Defining quality is the PM's job |
| Framework setup & boilerplate | Claude | Mechanical wiring of pytest, LangSmith, fixtures |
| Writing individual eval cases | Split | Claude drafts, human reviews and adds edge cases |
| LangSmith dataset creation | Claude | Mechanical upload |
| Evaluator logic (LLM-as-judge prompts) | Split | Human defines "correct", Claude implements |
| Interpreting results & writing summary | Human | Interviewer wants your analysis |
| Live demo prep | Both | Rehearse making agent changes and re-running evals |

## What's Next
- Lock down final eval categories and specific test cases
- Build the eval framework (pytest + notebook for live demo)
- Implement evals with evaluators (programmatic checks + LLM-as-judge)
- Record to LangSmith for observability
- Prep for live demo (model swap, prompt change, tool change scenarios)
