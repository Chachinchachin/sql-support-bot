# SQL Support Bot

Customer support chatbot for a music store (Chinook database) built with DeepAgents + LangChain.

## Setup

```bash
uv sync
cp .env.example .env  # fill in your keys
```

Requires: `OPENAI_API_KEY`. Optional: LangSmith keys for tracing.

## Running

```bash
# Interactive chat
uv run python agent.py

# Create LangSmith dataset from existing traces
uv run python create_dataset.py

# Run simulated multi-turn conversation (LLM plays the customer)
uv run python simulate_conversation.py
```

## Architecture

- **agent.py** — Main bot. Uses `create_deep_agent` with 4 SQL tools (albums, tracks, songs, customer info). Each conversation gets a `thread_id` passed via LangChain config metadata for LangSmith trace linking.
- **create_dataset.py** — Fetches traces from LangSmith REST API, groups them into conversations, creates a LangSmith dataset, optionally re-runs with thread_id linking.
- **simulate_conversation.py** — Uses `openevals` (`run_multiturn_simulation` + `create_llm_simulated_user`) to run a simulated customer conversation. Has a stop condition to end when both sides say goodbye. Max 30 turns.

## LangSmith

- Project: `langsmith-sql-bot`
- All traces are linked by `thread_id` in metadata
- View conversations in the **Threads** tab
- Query traces: `client.list_runs(project_name="langsmith-sql-bot", filter='eq(metadata.thread_id, "<id>")')`

## Key decisions

- Database is Chinook (downloaded into in-memory SQLite on startup)
- `openevals` package used for simulated conversations (not the older LangGraph simulation approach)
- Thread linking uses LangSmith metadata (`thread_id` key), not LangGraph checkpointers
