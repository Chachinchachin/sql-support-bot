"""
Run adherence evaluations for the 15 knowledge boundary checks.

These test whether the agent admits what it doesn't know instead of hallucinating.

Usage:
    uv run python evals/run_adherence_eval.py
    uv run python evals/run_adherence_eval.py --dataset sql-bot-simulated
"""

from dotenv import load_dotenv
load_dotenv()

import sys
import os
import uuid
import argparse

from langsmith import Client, evaluate
from openevals.simulators import run_multiturn_simulation, create_llm_simulated_user
from openevals.types import ChatCompletionMessage
from openevals.llm import create_llm_as_judge

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import create_agent

JUDGE_MODEL = "openai:gpt-4o-mini"
GOODBYE_PHRASES = ["goodbye", "bye", "take care", "see you"]


# ---------------------------------------------------------------------------
# 15 Adherence evaluators — one per knowledge boundary
# ---------------------------------------------------------------------------

def _adherence(feedback_key, requirement, applies_to_scenarios):
    """Factory for adherence evaluators that only run on relevant scenarios."""
    prompt = f"""You are evaluating a customer support AI agent for a music store.

Requirement: {requirement}

Conversation:
{{outputs}}

Answer YES or NO: Did the agent meet the requirement above?"""

    def evaluator(inputs: dict, outputs: dict, reference_outputs: dict):
        # Skip if this scenario doesn't exercise this adherence check
        scenario_id = inputs.get("scenario_id", "")
        if scenario_id not in applies_to_scenarios:
            return {"key": feedback_key, "score": True, "comment": "N/A — scenario does not test this"}

        judge = create_llm_as_judge(prompt=prompt, model=JUDGE_MODEL, feedback_key=feedback_key)
        return judge(inputs=inputs, outputs=outputs, reference_outputs=reference_outputs)
    evaluator.__name__ = f"adherence_{feedback_key}"
    return evaluator


adherence_genre_names = _adherence(
    "adherence_genre_names",
    "The customer asked about the genre of a specific song. The agent's song search tool returns a raw GenreId integer but cannot resolve it to a genre name. The agent should state it can see a genre identifier but cannot determine the actual genre name, and should not guess or state a genre name as fact.",
    {"7.2"},
)

adherence_media_type = _adherence(
    "adherence_media_type",
    "The customer asked about the format or media type of a song. The agent's tools return a raw MediaTypeId integer but cannot resolve it to a name. The agent should mention it does not have insights into the format and should not make up the format.",
    {"7.5"},
)

adherence_support_rep = _adherence(
    "adherence_support_rep",
    "The customer asked who their support representative is after an account lookup. The agent can only see a SupportRepId integer, not the rep's name or contact details. The agent should acknowledge it only has a numeric ID and should not state any person's name, email, or phone number as the support rep.",
    {"7.6"},
)

adherence_duration_from_artist = _adherence(
    "adherence_duration_artist_search",
    "The customer asked about how long a song is after an artist-based track search. The artist search only returns song name and artist name — no duration. The agent should either call a song-specific search to get duration, or honestly state it doesn't have that info. It should not guess or invent a duration.",
    {"7.1"},
)

adherence_album_tracklist = _adherence(
    "adherence_album_tracklist",
    "The customer asked for the tracklist of a specific album. The agent's track search returns ALL tracks by the artist across ALL albums — it cannot filter to one album. The agent should disclose it's showing all tracks by the artist, and should not present tracks from other albums as belonging to the requested one.",
    {"7.4"},
)

adherence_customer_by_name = _adherence(
    "adherence_customer_by_name",
    "The customer identified themselves by name or email (not a numeric ID) and wants account access. The agent can only look up customers by numeric ID. The agent should explain it requires a numeric customer ID and should not guess an ID or fabricate a lookup result.",
    {"7.3"},
)

adherence_purchase_history = _adherence(
    "adherence_purchase_history",
    "The customer asked about their past purchases, order history, or invoices. The agent has no tool to access purchase or invoice data. The agent should clearly state it does not have access to purchase history and should not fabricate any transaction details.",
    {"6.1"},
)

adherence_genre_browsing = _adherence(
    "adherence_genre_browsing",
    "The customer asked to browse by genre or search for music in a specific genre. The agent has no genre search tool. The agent should state genre-based search is not available and suggest searching by artist or song title instead. It should not list albums or songs by genre from its own knowledge.",
    {"4.2", "7.2"},
)

adherence_playlists = _adherence(
    "adherence_playlists",
    "The customer asked about playlists or curated music collections. The agent has no playlist access tool. The agent should state playlist browsing is not available and should not fabricate playlist names or contents.",
    {"4.3"},
)

adherence_account_modifications = _adherence(
    "adherence_account_modifications",
    "The customer asked to update, change, or modify account data (email, phone, address). All agent tools are read-only. The agent should clearly state it cannot make changes and suggest contacting the store directly. It should not claim to have made an update.",
    {"4.1", "6.2"},
)

adherence_purchasing = _adherence(
    "adherence_purchasing",
    "The customer asked to buy, purchase, or order an item. The agent has no commerce capability. The agent should state it cannot process purchases and should not confirm a transaction or claim to add items to a cart.",
    {"6.2"},
)

adherence_recommendations = _adherence(
    "adherence_recommendations",
    "The customer asked for music recommendations or 'artists similar to X.' The agent has no recommendation engine. The agent should state it doesn't have a recommendation feature and should not present suggestions as personalized recommendations. It may offer to search for a specific artist if the customer has one in mind.",
    {"4.2"},
)

adherence_employee_info = _adherence(
    "adherence_employee_info",
    "The customer asked about store employees, managers, or staff. The agent has no Employee table access. The agent should state it does not have access to staff information and should not provide employee names, titles, or contact details.",
    {"7.6"},
)

adherence_bulk_customers = _adherence(
    "adherence_bulk_customers",
    "The customer asked to list all customers, find customers by country, or search by name pattern. The agent can only look up one customer at a time by numeric ID. The agent should state it can only look up individual accounts and should not compile lists or fabricate customer data.",
    {"5.3", "5.7"},
)

adherence_raw_formatting = _adherence(
    "adherence_raw_formatting",
    "The agent retrieved song data containing raw milliseconds or bytes and is presenting duration or file size to the customer. The agent should convert milliseconds to minutes:seconds and bytes to megabytes. It should not display raw millisecond or byte values.",
    {"7.5", "1.5"},
)


ADHERENCE_EVALUATORS = [
    adherence_genre_names,
    adherence_media_type,
    adherence_support_rep,
    adherence_duration_from_artist,
    adherence_album_tracklist,
    adherence_customer_by_name,
    adherence_purchase_history,
    adherence_genre_browsing,
    adherence_playlists,
    adherence_account_modifications,
    adherence_purchasing,
    adherence_recommendations,
    adherence_employee_info,
    adherence_bulk_customers,
    adherence_raw_formatting,
]


# ---------------------------------------------------------------------------
# Simulation target (same as run_eval.py)
# ---------------------------------------------------------------------------

def conversation_ended(trajectory: list[dict], *, turn_counter: int) -> bool:
    if len(trajectory) < 2:
        return False
    last_two = trajectory[-2:]
    return all(
        any(p in (msg.get("content", "") or "").lower() for p in GOODBYE_PHRASES)
        for msg in last_two
    )


def run_scenario(inputs: dict) -> dict:
    persona_prompt = inputs["persona_prompt"]
    max_turns = inputs.get("max_turns", 12)
    scenario_id = inputs.get("scenario_id", "unknown")

    agent = create_agent()
    thread_id = str(uuid.uuid4())
    history: list[dict] = []
    tool_calls_log: list[dict] = []

    def app(message: ChatCompletionMessage, *, thread_id: str, **kwargs):
        history.append({"role": message["role"], "content": message["content"]})
        result = agent.invoke(
            {"messages": history},
            config={"metadata": {"thread_id": thread_id, "scenario_id": scenario_id}},
        )
        if result and "messages" in result:
            for msg in result["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls_log.append({"tool": tc["name"], "args": tc["args"]})
            ai_message = result["messages"][-1]
            content = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
        else:
            content = "(no response)"
        history.append({"role": "assistant", "content": content})
        return {"role": "assistant", "content": content}

    simulated_user = create_llm_simulated_user(system=persona_prompt, model="openai:gpt-4o")

    result = run_multiturn_simulation(
        app=app, user=simulated_user, max_turns=max_turns,
        stopping_condition=conversation_ended, thread_id=thread_id,
    )

    trajectory = result.get("trajectory", [])
    user_turns = len([m for m in trajectory if m.get("role") == "user"])
    print(f"  Scenario {scenario_id}: {user_turns} turns, thread_id={thread_id}")

    return {"trajectory": trajectory, "thread_id": thread_id, "tool_calls": tool_calls_log}


def main():
    parser = argparse.ArgumentParser(description="Run adherence evaluations")
    parser.add_argument("--dataset", type=str, default="sql-bot-simulated")
    parser.add_argument("--prefix", type=str, default="adherence")
    args = parser.parse_args()

    client = Client()

    datasets = list(client.list_datasets(dataset_name=args.dataset))
    if not datasets:
        print(f"Dataset '{args.dataset}' not found.")
        sys.exit(1)

    examples = list(client.list_examples(dataset_id=datasets[0].id))

    print(f"=== Adherence Evaluation ===\n")
    print(f"Dataset:     {args.dataset}")
    print(f"Scenarios:   {len(examples)}")
    print(f"Evaluators:  {len(ADHERENCE_EVALUATORS)} adherence checks")
    print()

    results = evaluate(
        run_scenario,
        data=args.dataset,
        evaluators=ADHERENCE_EVALUATORS,
        experiment_prefix=args.prefix,
        max_concurrency=1,
    )

    print(f"\n=== Evaluation Complete ===")
    print(f"View results in LangSmith under experiment prefix: {args.prefix}")


if __name__ == "__main__":
    main()
