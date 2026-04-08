"""
Run SQL Support Bot evaluations via LangSmith.

Usage:
    # Run all scenarios:
    uv run python evals/run_eval.py

    # Run a specific skill:
    uv run python evals/run_eval.py --skill security
    uv run python evals/run_eval.py --skill cross_use_case

    # Run against a specific dataset:
    uv run python evals/run_eval.py --dataset sql-bot-security

    # Custom experiment prefix:
    uv run python evals/run_eval.py --skill security --prefix security-v2

Available skills: cross_use_case, security, conversation, account, music, boundary, data_quality
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

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import create_agent
from evals.evaluators import ALL_EVALUATORS
from evals.scenarios import SKILL_NAMES

GOODBYE_PHRASES = ["goodbye", "bye", "take care", "see you"]


def conversation_ended(trajectory: list[dict], *, turn_counter: int) -> bool:
    """Stop when both user and assistant have said goodbye."""
    if len(trajectory) < 2:
        return False
    last_two = trajectory[-2:]
    return all(
        any(p in (msg.get("content", "") or "").lower() for p in GOODBYE_PHRASES)
        for msg in last_two
    )


def run_scenario(inputs: dict) -> dict:
    """
    Target function for langsmith.evaluate().

    Supports three scenario shapes:
    1. Persona-driven (default) — `inputs["persona_prompt"]` drives an LLM-powered
       simulated customer. Uses `run_multiturn_simulation` from openevals.
    2. Direct messages — `inputs["messages"]` is a list of pre-written user
       messages sent directly to the agent without a simulator. Used for
       single-shot adversarial tests where the exact prompt matters.
    3. Multi-session — `inputs["sessions"]` is a list of `{user, content}`
       items. Each unique `user` label gets its own thread_id (and its own
       conversation history) but they all share ONE agent instance — this is
       the production-realistic multi-tenant pattern. Used to test cross-user
       state leakage via the virtual filesystem.
    """
    scenario_id = inputs.get("scenario_id", "unknown")

    agent = create_agent()
    thread_id = str(uuid.uuid4())
    tool_calls_log: list[dict] = []

    def _capture_tool_calls(result):
        if result and "messages" in result:
            for msg in result["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls_log.append({"tool": tc["name"], "args": tc["args"]})

    # ----- Multi-session shape: shared agent instance, distinct thread_ids -----
    if "sessions" in inputs:
        # Build per-user histories and thread IDs
        user_histories: dict[str, list[dict]] = {}
        user_threads: dict[str, str] = {}
        trajectory: list[dict] = []

        for turn in inputs["sessions"]:
            user_label = turn["user"]
            if user_label not in user_threads:
                user_threads[user_label] = str(uuid.uuid4())
                user_histories[user_label] = []

            history = user_histories[user_label]
            t_id = user_threads[user_label]

            user_msg = {"role": "user", "content": turn["content"]}
            history.append(user_msg)
            trajectory.append({"role": "user", "content": f"[{user_label}] {turn['content']}"})

            result = agent.invoke(
                {"messages": history},
                config={"metadata": {"thread_id": t_id, "scenario_id": scenario_id, "user_label": user_label}},
            )
            _capture_tool_calls(result)

            if result and "messages" in result:
                ai_message = result["messages"][-1]
                content = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
            else:
                content = "(no response)"
            history.append({"role": "assistant", "content": content})
            trajectory.append({"role": "assistant", "content": f"[to {user_label}] {content}"})

        print(f"  Scenario {scenario_id}: multi-session ({len(user_threads)} users, {len(inputs['sessions'])} turns)")
        return {
            "trajectory": trajectory,
            "thread_id": list(user_threads.values())[0],  # primary thread for tracing
            "tool_calls": tool_calls_log,
        }

    # ----- Direct-message shape: send pre-written messages, no simulator -----
    if "messages" in inputs:
        history: list[dict] = []
        trajectory: list[dict] = []
        for user_msg in inputs["messages"]:
            history.append({"role": user_msg["role"], "content": user_msg["content"]})
            trajectory.append({"role": user_msg["role"], "content": user_msg["content"]})

            result = agent.invoke(
                {"messages": history},
                config={"metadata": {"thread_id": thread_id, "scenario_id": scenario_id}},
            )
            _capture_tool_calls(result)

            if result and "messages" in result:
                ai_message = result["messages"][-1]
                content = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
            else:
                content = "(no response)"
            history.append({"role": "assistant", "content": content})
            trajectory.append({"role": "assistant", "content": content})

        print(f"  Scenario {scenario_id}: direct ({len(inputs['messages'])} msg), thread_id={thread_id}")
        return {
            "trajectory": trajectory,
            "thread_id": thread_id,
            "tool_calls": tool_calls_log,
        }

    # ----- Persona-driven shape: full multi-turn simulation -----
    persona_prompt = inputs["persona_prompt"]
    max_turns = inputs.get("max_turns", 12)
    history: list[dict] = []

    def app(message: ChatCompletionMessage, *, thread_id: str, **kwargs):
        history.append({"role": message["role"], "content": message["content"]})

        result = agent.invoke(
            {"messages": history},
            config={"metadata": {"thread_id": thread_id, "scenario_id": scenario_id}},
        )
        _capture_tool_calls(result)

        if result and "messages" in result:
            ai_message = result["messages"][-1]
            content = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
        else:
            content = "(no response)"

        history.append({"role": "assistant", "content": content})
        return {"role": "assistant", "content": content}

    simulated_user = create_llm_simulated_user(
        system=persona_prompt,
        model="openai:gpt-4o",
    )

    result = run_multiturn_simulation(
        app=app,
        user=simulated_user,
        max_turns=max_turns,
        stopping_condition=conversation_ended,
        thread_id=thread_id,
    )

    trajectory = result.get("trajectory", [])
    user_turns = len([m for m in trajectory if m.get("role") == "user"])
    print(f"  Scenario {scenario_id}: {user_turns} turns, thread_id={thread_id}")

    return {
        "trajectory": trajectory,
        "thread_id": thread_id,
        "tool_calls": tool_calls_log,
    }


def main():
    parser = argparse.ArgumentParser(description="Run SQL bot evaluations")
    parser.add_argument("--skill", type=str, default=None,
                        help="Run only a specific skill's dataset")
    parser.add_argument("--dataset", type=str, default=None,
                        help="Run against a specific dataset name")
    parser.add_argument("--prefix", type=str, default=None,
                        help="Custom experiment prefix")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Max concurrent scenarios (default: 1)")
    args = parser.parse_args()

    client = Client()

    # Determine dataset name
    if args.dataset:
        dataset_name = args.dataset
    elif args.skill:
        dataset_name = f"sql-bot-{args.skill.replace('_', '-')}"
    else:
        dataset_name = "sql-bot-simulated"

    # Determine experiment prefix
    if args.prefix:
        experiment_prefix = args.prefix
    elif args.skill:
        experiment_prefix = f"sql-bot-{args.skill.replace('_', '-')}"
    else:
        experiment_prefix = "sql-bot-simulated"

    # Verify dataset exists
    datasets = list(client.list_datasets(dataset_name=dataset_name))
    if not datasets:
        print(f"Dataset '{dataset_name}' not found. Create it first:")
        print(f"  uv run python evals/create_dataset.py")
        if args.skill:
            print(f"  uv run python evals/create_dataset.py --skill {args.skill}")
        sys.exit(1)

    # Count examples
    examples = list(client.list_examples(dataset_id=datasets[0].id))
    skill_label = SKILL_NAMES.get(args.skill, "All") if args.skill else "All"

    print(f"=== SQL Bot Evaluation ===\n")
    print(f"Dataset:     {dataset_name}")
    print(f"Skill:       {skill_label}")
    print(f"Scenarios:   {len(examples)}")
    print(f"Evaluators:  {len(ALL_EVALUATORS)}")
    print(f"Experiment:  {experiment_prefix}")
    print()

    results = evaluate(
        run_scenario,
        data=dataset_name,
        evaluators=ALL_EVALUATORS,
        experiment_prefix=experiment_prefix,
        max_concurrency=args.concurrency,
    )

    print(f"\n=== Evaluation Complete ===\n")
    print(f"View results in LangSmith:")
    print(f"  Dataset: {dataset_name}")
    print(f"  Experiment prefix: {experiment_prefix}")


if __name__ == "__main__":
    main()
