"""
Create LangSmith datasets for the SQL Support Bot test suite.

Usage:
    # Create all datasets (one per skill):
    uv run python evals/create_dataset.py

    # Create a specific skill's dataset:
    uv run python evals/create_dataset.py --skill security
    uv run python evals/create_dataset.py --skill cross_use_case

Available skills: cross_use_case, security, conversation, account, music, boundary, data_quality
"""

from dotenv import load_dotenv
load_dotenv()

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client
from evals.scenarios import SCENARIOS, SKILL_NAMES, get_scenarios_by_skill

DATASET_PREFIX = "sql-bot"


def create_dataset_for_skill(client: Client, skill: str, scenarios: list[dict]):
    """Create or replace a dataset for a given skill."""
    dataset_name = f"{DATASET_PREFIX}-{skill.replace('_', '-')}"
    description = f"{SKILL_NAMES.get(skill, skill)} test scenarios for the SQL Support Bot"

    # Delete existing
    try:
        datasets = list(client.list_datasets(dataset_name=dataset_name))
        if datasets:
            client.delete_dataset(dataset_id=datasets[0].id)
            print(f"  Replaced existing dataset: {dataset_name}")
    except Exception:
        pass

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=description,
    )

    client.create_examples(
        dataset_id=dataset.id,
        examples=scenarios,
    )

    print(f"  Created: {dataset_name} ({len(scenarios)} scenarios)")
    return dataset


def create_simulated_dataset(client: Client):
    """Create the unified `sql-bot-simulated` dataset with all scenarios."""
    dataset_name = f"{DATASET_PREFIX}-simulated"
    description = "All 34 simulated test scenarios for the SQL Support Bot"

    try:
        datasets = list(client.list_datasets(dataset_name=dataset_name))
        if datasets:
            client.delete_dataset(dataset_id=datasets[0].id)
    except Exception:
        pass

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=description,
    )

    client.create_examples(
        dataset_id=dataset.id,
        examples=SCENARIOS,
    )

    print(f"  Created: {dataset_name} ({len(SCENARIOS)} scenarios)")
    return dataset


def main():
    parser = argparse.ArgumentParser(description="Create LangSmith datasets for SQL bot eval")
    parser.add_argument("--skill", type=str, default=None,
                        help="Create dataset for a specific skill only")
    args = parser.parse_args()

    client = Client()
    print("=== Creating LangSmith Datasets ===\n")

    if args.skill:
        scenarios = get_scenarios_by_skill(args.skill)
        if not scenarios:
            print(f"No scenarios found for skill: {args.skill}")
            print(f"Available: {', '.join(SKILL_NAMES.keys())}")
            return
        create_dataset_for_skill(client, args.skill, scenarios)
    else:
        # Create per-skill datasets + the unified `sql-bot-simulated` dataset
        skills = {}
        for s in SCENARIOS:
            skill = s["inputs"].get("skill", "unknown")
            skills.setdefault(skill, []).append(s)

        for skill, scenarios in skills.items():
            create_dataset_for_skill(client, skill, scenarios)

        create_simulated_dataset(client)

    print(f"\nRun evaluations with:")
    print(f"  uv run python evals/run_eval.py")
    print(f"  uv run python evals/run_eval.py --skill security")
    print(f"  uv run python evals/run_eval.py --dataset sql-bot-simulated")


if __name__ == "__main__":
    main()
