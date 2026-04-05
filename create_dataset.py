"""
Pull existing traces from LangSmith, group them into conversations,
create a dataset, and re-run to verify thread_id linking works.
"""

from dotenv import load_dotenv
load_dotenv()

import json
import os
import uuid
import requests
from langsmith import Client

API_KEY = os.environ.get("LANGSMITH_API_KEY", "")
SESSION_ID = os.environ.get("LANGSMITH_SESSION_ID", "208fe9a8-0068-4d54-b520-109fdf4e7225")
DATASET_NAME = "sql-bot-conversations"


def fetch_traces():
    """Fetch all root traces from the LangSmith project."""
    headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}
    resp = requests.post(
        "https://api.smith.langchain.com/api/v1/runs/query",
        headers=headers,
        json={"session": [SESSION_ID], "is_root": True, "limit": 50},
    )
    runs = resp.json().get("runs", [])
    runs.sort(key=lambda r: r["start_time"])
    return runs


def group_into_conversations(runs):
    """
    Group traces into conversations. Since these traces come from one
    interactive session (each trace has growing message history), we
    reconstruct individual turn pairs from the incremental messages.
    """
    conversations = {}

    # All 18 traces are from one conversation session - extract the
    # individual turn pairs (user question -> assistant answer)
    conversation_id = "conv-1"
    turns = []

    for run in runs:
        input_msgs = run.get("inputs", {}).get("messages", [])
        output_msgs = run.get("outputs", {}).get("messages", [])

        # Get the last human message from inputs (the new user question)
        human_msgs = [m for m in input_msgs if m.get("role") == "user"]
        if not human_msgs:
            continue

        last_human = human_msgs[-1]["content"]

        # Get the last AI message from outputs (uses type: "ai", not role)
        ai_content = ""
        if output_msgs:
            ai_msgs = [m for m in output_msgs if m.get("type") == "ai"]
            if ai_msgs:
                ai_content = ai_msgs[-1].get("content", "") or ""

        if last_human and ai_content:
            turns.append({
                "turn_number": len(turns) + 1,
                "user": last_human,
                "assistant": ai_content,
                "trace_id": run["id"],
                "timestamp": run["start_time"],
            })

    conversations[conversation_id] = {
        "conversation_id": conversation_id,
        "turns": turns,
        "total_turns": len(turns),
    }

    return conversations


def create_langsmith_dataset(conversations):
    """Create a LangSmith dataset from the grouped conversations."""
    client = Client(api_key=API_KEY)

    # Create or get the dataset
    try:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Conversations extracted from sql-bot traces for replay testing",
        )
        print(f"Created dataset: {DATASET_NAME} (id: {dataset.id})")
    except Exception:
        # Dataset may already exist
        datasets = list(client.list_datasets(dataset_name=DATASET_NAME))
        if datasets:
            dataset = datasets[0]
            print(f"Using existing dataset: {DATASET_NAME} (id: {dataset.id})")
        else:
            raise

    # Add each conversation turn as an example
    for conv_id, conv in conversations.items():
        for turn in conv["turns"]:
            # Build the message history up to this turn
            history = []
            for prev_turn in conv["turns"]:
                if prev_turn["turn_number"] > turn["turn_number"]:
                    break
                if prev_turn["turn_number"] < turn["turn_number"]:
                    history.append({"role": "user", "content": prev_turn["user"]})
                    history.append({"role": "assistant", "content": prev_turn["assistant"]})

            # Current turn's user message
            history.append({"role": "user", "content": turn["user"]})

            client.create_example(
                inputs={
                    "messages": history,
                    "conversation_id": conv_id,
                    "turn_number": turn["turn_number"],
                },
                outputs={
                    "expected_response": turn["assistant"],
                },
                dataset_id=dataset.id,
            )

        print(f"  Added {len(conv['turns'])} turns from {conv_id}")

    return dataset


def run_dataset_with_thread_ids(dataset):
    """
    Re-run the dataset examples through the agent to verify
    that thread_id linking works in LangSmith.
    """
    from agent import create_agent

    agent = create_agent()
    client = Client(api_key=API_KEY)

    examples = list(client.list_examples(dataset_id=dataset.id))
    examples.sort(key=lambda e: (e.inputs.get("conversation_id", ""), e.inputs.get("turn_number", 0)))

    # Group examples by conversation_id
    conv_examples = {}
    for ex in examples:
        cid = ex.inputs.get("conversation_id", "unknown")
        conv_examples.setdefault(cid, []).append(ex)

    print(f"\nRe-running {len(examples)} examples across {len(conv_examples)} conversations...\n")

    for conv_id, exs in conv_examples.items():
        thread_id = str(uuid.uuid4())
        print(f"Conversation: {conv_id} -> thread_id: {thread_id}")

        for ex in exs:
            messages = ex.inputs["messages"]
            turn = ex.inputs.get("turn_number", "?")

            result = agent.invoke(
                {"messages": messages},
                config={"metadata": {"thread_id": thread_id, "conversation_id": conv_id}},
            )

            if result and "messages" in result:
                ai_msg = result["messages"][-1]
                content = ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)
                print(f"  Turn {turn}: {content[:80]}...")
            else:
                print(f"  Turn {turn}: (no response)")

        print(f"  All turns linked under thread_id: {thread_id}")
        print(f"  View in LangSmith Threads tab to verify!\n")


if __name__ == "__main__":
    print("=== Step 1: Fetching existing traces ===\n")
    runs = fetch_traces()
    print(f"Found {len(runs)} root traces\n")

    print("=== Step 2: Grouping into conversations ===\n")
    conversations = group_into_conversations(runs)
    for cid, conv in conversations.items():
        print(f"  {cid}: {conv['total_turns']} turns")
        for t in conv["turns"]:
            print(f"    Turn {t['turn_number']}: \"{t['user'][:60]}\"")
    print()

    print("=== Step 3: Creating LangSmith dataset ===\n")
    dataset = create_langsmith_dataset(conversations)
    print()

    answer = input("Run dataset through agent to test thread linking? (y/n): ")
    if answer.lower() == "y":
        print("\n=== Step 4: Re-running with thread_id ===\n")
        run_dataset_with_thread_ids(dataset)
    else:
        print("\nDataset created. Run later with: uv run python create_dataset.py")
