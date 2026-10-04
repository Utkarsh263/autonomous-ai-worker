"""
Very small working memory for a single task run.

This is deliberately simple: a dict of facts the agent has learned while
working, plus a running list of the steps it took. A "real" system might
use a vector store or a database, but for a prototype that completes one
task at a time, an in-memory object that lives for the duration of the run
is enough -- and it's easy to reason about and debug.
"""

from datetime import datetime


class WorkingMemory:
    def __init__(self):
        self.facts = {}          # things discovered during the run (e.g. which file is "latest")
        self.steps = []          # full trace of actions + observations, used for the final report

    def remember(self, key, value):
        self.facts[key] = value

    def recall(self, key, default=None):
        return self.facts.get(key, default)

    def log_step(self, action, detail, result):
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "detail": detail,
            "result": result,
        }
        self.steps.append(entry)
        return entry
