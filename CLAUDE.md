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

## Repository files

### Active code

| File | Purpose |
|------|---------|
| `agent.py` | Main bot. Uses `create_deep_agent` with 4 SQL tools (albums, tracks, songs, customer info). Each conversation gets a `thread_id` passed via LangChain config metadata for LangSmith trace linking. Also serves as the interactive REPL when run directly. |
| `simulate_conversation.py` | Standalone script using `openevals` (`run_multiturn_simulation` + `create_llm_simulated_user`) to run a one-off simulated customer conversation against the agent. Max 30 turns, stops on mutual goodbye. Predates the eval suite — kept for ad-hoc demos. |
| `create_dataset.py` | Standalone script that fetches existing traces from LangSmith via the REST API, groups them into conversations, and creates a LangSmith dataset from production traffic. Different from `evals/create_dataset.py` (which uploads curated scenarios). |
| `evals/scenarios.py` | 44 test scenarios (35 persona-driven + 8 single-shot adversarial probes + 1 multi-session covert-channel test). Source of truth for the eval suite. |
| `evals/evaluators.py` | 65 evaluators (tool-call, LLM-as-judge, regex, red-team graders, promise adherence, tool-call budget, crash detection) + 1 POC trace-based evaluator. Notes: (1) `no_unexpected_tools` was removed — too many false positives flagging legitimate follow-up calls and DeepAgents built-ins (ls, grep, read_file). (2) `eval_agent_did_not_crash` is the one evaluator that always runs and surfaces agent crashes as a dedicated FAIL — all other evaluators return N/A on crashed scenarios via `_is_crashed()` so the underlying bug isn't drowned in 60+ false alarms. |
| `evals/create_dataset.py` | Uploads scenarios from `scenarios.py` to LangSmith as datasets (per-skill + the unified `sql-bot-simulated`). |
| `evals/run_eval.py` | Runs the full evaluation suite via `langsmith.evaluate()`. Supports `--skill`, `--dataset`, `--prefix` flags. |
| `evals/run_adherence_eval.py` | Runs only the 15 knowledge-boundary adherence checks. Lighter-weight than the full suite. |
| `pyproject.toml` | Dependencies (managed via `uv`). |
| `.env.example` | Template for required env vars. |

### Markdown documentation

| File | What's in it |
|------|-------------|
| `README.md` | User-facing quickstart for the agent itself. Setup, usage, example queries. Doesn't cover the eval suite. |
| `CLAUDE.md` | This file. Project documentation for Claude (and humans) — architecture, conventions, eval suite, key decisions. |
| `analysis/SUMMARY.md` | Original session-summary doc from the eval planning phase. Frames the project as a PM interview take-home, lists the 4 tools, the user-journey questions, and division of labor between human and Claude. Historical context. |
| `analysis/AGENT-INCONSISTENCIES.md` | The 9 design inconsistencies in the agent (tool richness mismatch, foreign key resolution, no purchase history, name lookup, etc.) with impact analysis. Source for several of the data quality / boundary scenarios in `evals/scenarios.py`. |
| `analysis/SQL-TABLE-EXAMPLE.md` | Schema reference for the Chinook database — all 11 tables with sample rows and a note on which tables each tool can access. Useful for writing scenarios that reference real customer IDs / songs. |
| `evals/desired_behaviors.md` | 15 documented knowledge gaps with binary adherence requirements. Each gap has: what the agent can't do, what it *should* say, what's unacceptable, and a pre-condition + binary YES/NO requirement. Source for the adherence evaluators in `evals/run_adherence_eval.py`. |

## LangSmith

### Tracing project
- Project: `langsmith-sql-bot`
- All traces are linked by `thread_id` in metadata
- View conversations in the **Threads** tab
- Query traces: `client.list_runs(project_name="langsmith-sql-bot", filter='eq(metadata.thread_id, "<id>")')`

### Datasets (offline evaluation)

| Dataset | Scenarios | Purpose |
|---------|-----------|---------|
| `sql-bot-simulated` | 44 | All scenarios merged — primary dataset for end-to-end evaluation |
| `sql-bot-adherence` | 11 | Subset of scenarios that test knowledge boundary gaps |
| `sql-bot-cross-use-case` | 3 | Multi-skill scenarios (6.1–6.3) |
| `sql-bot-security` | 18 | SQL injection, prompt extraction, jailbreak, FS abuse, cross-session covert channel, recursive loops, tool disclosure (5.1–5.18) |
| `sql-bot-conversation` | 3 | Multi-turn context, recovery, long sessions (3.1–3.3) |
| `sql-bot-account` | 4 | Customer account management (2.1–2.4) |
| `sql-bot-music` | 5 | Music catalog discovery (1.1–1.5) |
| `sql-bot-boundary` | 4 | Out-of-scope handling (4.1–4.4) |
| `sql-bot-data-quality` | 7 | Data quality + agent inconsistencies (7.1–7.7) |

The 7 per-skill datasets sum to exactly 44 — same scenarios as `sql-bot-simulated`. Use `sql-bot-simulated` to run everything in one experiment, or per-skill datasets for targeted runs.

### Scenario shapes

`run_eval.py` supports three scenario shapes:

1. **Persona-driven** (35 scenarios) — `inputs["persona_prompt"]` drives a `create_llm_simulated_user` that talks to the agent for up to N turns. Best for behavioral / multi-turn tests. Always cap with `max_turns` (default 12, up to 30 for resource-exhaustion tests).
2. **Single-shot** (8 scenarios, all in security: 5.9-5.15, 5.17) — `inputs["messages"]` is a list of pre-written user messages sent directly to the agent without a simulator. Best for adversarial tests where the exact prompt matters and the LLM-customer might paraphrase or refuse to deliver it.
3. **Multi-session** (1 scenario, 5.18) — `inputs["sessions"]` is a list of `{user, content}` items where each unique `user` label gets its own `thread_id` but all share ONE agent instance. Used to test cross-user state leakage (covert channels via the DeepAgents virtual filesystem).

### Experiment projects (where eval results land)

Experiments are auto-named with the prefix passed to `--prefix`. Each `evaluate()` run creates a new project under that prefix in LangSmith. Recent runs:

| Project name | What it ran |
|--------------|-------------|
| `codereview-smoke-*` | Account scenarios after the code-review fixes (validates `score=None` for N/A) |
| `adherence-v3-*` | 15 adherence checks against `sql-bot-simulated` (latest, scoped via scenario IDs) |
| `adherence-v2-*` | Adherence checks with stricter pre-condition prompt (LLM still failed pre-conditions) |
| `adherence-v1-*` | First adherence run; pre-conditions handled by LLM (had false positives) |
| `cross-use-case-prebuilt-v2-*` | Cross-use-case + prebuilt openevals (correctness/hallucination/etc.) |
| `cross-use-case-with-prebuilt-*` | Same as above, earlier version with bug |
| `smoke-test-*` | Account management smoke test |

## Running evaluations

```bash
# Create / refresh all datasets
uv run python evals/create_dataset.py

# Run all 44 scenarios with all 65 evaluators
uv run python evals/run_eval.py

# Run a single skill
uv run python evals/run_eval.py --skill security
uv run python evals/run_eval.py --skill cross_use_case

# Run only the 15 knowledge-boundary adherence checks
uv run python evals/run_adherence_eval.py --dataset sql-bot-simulated --prefix adherence-v4
```

## Scoring conventions

- **Skipped evaluators return `score=None`**, not `True`. LangSmith treats `None` as missing data and excludes it from aggregate averages, so a scenario that's only relevant to 11 of 61 evaluators shows as "11 applicable" instead of "61 passed." Earlier versions counted N/A as pass and inflated scores.
- **`expected_tools` semantics in `scenarios.py`:**
  - Omit (or `None`) → don't check tool calls (N/A)
  - `[]` → MUST call zero tools (used by security and boundary refusal scenarios)
  - `[...]` → only these tools allowed; all listed must be called
- **`expected_tool_args`** matches exact case-insensitive equality by default. Set `fuzzy_args: True` in the scenario's outputs to opt into word-boundary fuzzy matching (avoids substring false positives like `"AC"` matching `"BACH"`).
- **Promise adherence (`eval_promise_adherence`)** uses GPT-4o, not GPT-4o-mini, because pre-condition + comparison reasoning is exactly where mini struggles.

## Key decisions

- Database is Chinook (downloaded into in-memory SQLite on startup)
- `openevals` package used for simulated conversations (not the older LangGraph simulation approach)
- Thread linking uses LangSmith metadata (`thread_id` key), not LangGraph checkpointers
- Adherence pre-conditions are handled in **code** (scenario ID allowlist) rather than via LLM judge — GPT-4o-mini wasn't reliable at skipping irrelevant checks
- Tool-call evaluators are hand-rolled rather than using `agentevals.create_trajectory_match_evaluator` because that helper wasn't surfaced in the LangSmith eval quickstart we followed. Hand-rolled gives finer per-failure comments and lets us split "expected tools called" from "no unexpected tools" into two separate signals.
- Tool calls are captured manually in `run_eval.py`'s `app()` wrapper by inspecting `AIMessage.tool_calls`. A POC trace-based evaluator (`eval_expected_tools_called_from_trace`) exists in `evaluators.py` as `POC_TRACE_EVALUATORS` and uses `run.child_runs` instead — if it works reliably, the manual capture can be deleted.
- Custom evaluators live in code (`evals/evaluators.py`) and run via `langsmith.evaluate()`. They do NOT show up in the LangSmith UI's "Evaluators" tab — only UI-configured evaluators do. Both produce feedback scores in the same experiment view.
