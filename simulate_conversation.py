"""
Simulated multi-turn conversation with the SQL Support Bot.

Uses openevals to create an LLM-powered fake customer that talks to
our agent for up to 30 turns. All traces are linked under one thread_id.
"""

from dotenv import load_dotenv
load_dotenv()

import uuid
from openevals.simulators import run_multiturn_simulation, create_llm_simulated_user
from openevals.types import ChatCompletionMessage
from agent import create_agent

GOODBYE_PHRASES = ["goodbye", "bye", "take care", "see you"]


def conversation_ended(trajectory: list[dict], *, turn_counter: int) -> bool:
    """Stop when both user and assistant have said goodbye."""
    if len(trajectory) < 2:
        return False
    last_two = trajectory[-2:]
    return all(
        any(phrase in (msg.get("content", "") or "").lower() for phrase in GOODBYE_PHRASES)
        for msg in last_two
    )


def main():
    print("=== Simulated Conversation ===\n")
    print("Initializing agent...")
    agent = create_agent()

    thread_id = str(uuid.uuid4())
    print(f"Thread ID: {thread_id}\n")

    # Conversation history managed per thread
    history: list[dict] = []

    def app(message: ChatCompletionMessage, *, thread_id: str, **kwargs):
        """Wrap our agent to match the openevals app interface."""
        history.append({"role": message["role"], "content": message["content"]})

        result = agent.invoke(
            {"messages": history},
            config={"metadata": {"thread_id": thread_id}},
        )

        if result and "messages" in result:
            ai_message = result["messages"][-1]
            content = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
        else:
            content = "(no response)"

        history.append({"role": "assistant", "content": content})

        turn = len(history) // 2
        print(f"  Turn {turn}:")
        print(f"    User:      {message['content'][:100]}")
        print(f"    Assistant: {content[:100]}")
        print()

        return {"role": "assistant", "content": content}

    # Simulated customer persona
    simulated_user = create_llm_simulated_user(
        system="""You are a realistic customer of an online music store. You have a natural
conversation exploring different things you need help with. Follow this rough arc:

1. Start by greeting and asking what the store can help with.
2. Ask about music by a specific artist (try AC/DC or Led Zeppelin).
3. Search for a specific song title.
4. Ask about a different artist's albums.
5. Switch to account questions — say your customer ID is 3 and ask for your info.
6. Ask follow-up questions about your account details.
7. Try asking about something the bot can't do (like updating your email).
8. Circle back to music — ask about genres or recommendations.
9. Thank the bot and wrap up.

Be natural and conversational. Don't rush through topics — ask follow-up questions.
When you feel the conversation has naturally concluded, say "thanks, goodbye!" to end it.""",
        model="openai:gpt-4o",
    )

    print("Starting simulation (max 30 turns)...\n")

    result = run_multiturn_simulation(
        app=app,
        user=simulated_user,
        max_turns=30,
        stopping_condition=conversation_ended,
        thread_id=thread_id,
    )

    trajectory = result.get("trajectory", [])
    total_turns = len([m for m in trajectory if m.get("role") == "user"])

    print("=" * 60)
    print(f"\nSimulation complete!")
    print(f"  Total turns: {total_turns}")
    print(f"  Thread ID:   {thread_id}")
    print(f"\nView in LangSmith:")
    print(f"  Project: langsmith-sql-bot")
    print(f"  Threads tab -> look for thread_id: {thread_id}")
    print(f"\nQuery via SDK:")
    print(f"  from langsmith import Client")
    print(f"  client = Client()")
    print(f"  runs = client.list_runs(")
    print(f"      project_name='langsmith-sql-bot',")
    print(f"      filter='eq(metadata.thread_id, \"{thread_id}\")',")
    print(f"      is_root=True")
    print(f"  )")


if __name__ == "__main__":
    main()
