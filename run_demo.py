#!/usr/bin/env python3
"""
Entry point. Run with a natural-language task, e.g.:

    python run_demo.py "Find the latest invoice from Nimbus Traders, extract the amount and due date, enter it into our internal system, and tell me once it is done."

By default, if the agent needs to skip a broken invoice and use an older
one instead, it will pause and ask you (y/n) in the terminal -- that's the
human-approval step described in the brief. Pass --auto-approve to skip
the prompt (useful for a quick unattended demo / recording a run).
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.worker import run_task

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "run_log.jsonl")


DEFAULT_TASK = (
    "Find the latest invoice from Nimbus Traders, extract the amount and due date, "
    "enter it into our internal system, and tell me once it is done."
)


def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Task Worker (prototype)")
    parser.add_argument("task", nargs="?", default=DEFAULT_TASK, help="natural language task")
    parser.add_argument("--auto-approve", action="store_true", help="skip human-approval prompts")
    args = parser.parse_args()

    print(f"TASK: {args.task}\n")
    result = run_task(args.task, auto_approve=args.auto_approve)

    print("\n--- Execution trace ---")
    for step in result["trace"]:
        print(f"[{step['timestamp']}] {step['action']}: {step['detail']} -> {step['result']}")

    print("\n--- Final report ---")
    print(("SUCCESS: " if result["success"] else "FAILED: ") + result["summary"])

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(result, default=str) + "\n")
    print(f"\n(full trace appended to {LOG_PATH})")


if __name__ == "__main__":
    main()
