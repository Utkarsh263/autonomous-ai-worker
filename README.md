# Autonomous AI Task Worker (prototype)

A small prototype for the brief: *"Build a prototype of an AI worker that can take
a natural language task and autonomously attempt to complete it using a computer."*

Example task it handles:

> "Find the latest invoice from Nimbus Traders, extract the amount and due date,
> enter it into our internal system, and tell me once it is done."

This is a scoped, narrow prototype, not a production system -- per the brief's own
guidance, "a narrow prototype that genuinely works is better than a broad system
where most functionality is mocked." It uses a small local fake company environment
instead of a real website or a real accounting tool, so it's safe to run and share
(no real credentials, no third-party systems).

## What it actually does

Given a task sentence, the agent:

1. Figures out which company the task is about.
2. Looks through a folder of invoice files and finds the latest one for that company.
3. Reads it and pulls out the invoice number, amount, and due date.
4. **If that fails** (a field is missing or unparseable), it doesn't just crash --
   it logs the failure, falls back to the next most recent *valid* invoice for the
   same company, and **asks a human for approval** before using it instead of the one
   actually asked for.
5. Writes the result into a small JSON file that stands in for "our internal system,"
   checking first that it isn't a duplicate.
6. Reads the entry back out of that file to **verify** it's actually there (not just
   assuming the write worked).
7. Reports a plain-language summary of what it did, and why, if anything had to change.

Every step is logged with a timestamp, the action taken, and the result, so there's
a full trace of what the agent actually did -- not just what it was supposed to do.

## Project layout

```
autonomous-ai-worker/
├── run_demo.py                     # CLI entry point
├── agent/
│   ├── worker.py                   # the main plan -> act -> observe -> retry -> verify -> report loop
│   ├── tools.py                    # the only things the agent is allowed to do (read/write/verify)
│   ├── reasoner.py                 # turns the task sentence into a target (LLM optional, regex fallback)
│   └── memory.py                   # tiny working-memory object for one run (facts + step trace)
├── mock_company_app/
│   ├── invoices/                   # stand-in for "a shared drive full of invoices"
│   │   ├── invoice_101.txt         # Nimbus Traders, older, valid
│   │   ├── invoice_102.txt         # Nimbus Traders, newer, BROKEN on purpose (no amount, bad due date)
│   │   └── invoice_201.txt         # Bluepeak Solutions, valid (used to test generalization)
│   └── internal_system.json        # stand-in for "our internal system" -- the agent reads/writes this
└── logs/run_log.jsonl               # created on first run; one JSON line per run, full trace
```

## Setup & run

Requires Python 3.8+, no external dependencies for the core flow.

```bash
cd autonomous-ai-worker

# plain run, uses the default example task, asks for approval in the terminal
python3 run_demo.py

# your own task
python3 run_demo.py "Find the latest invoice from Bluepeak Solutions and enter it into our internal system."

# skip the interactive approval prompt (useful for a quick unattended demo)
python3 run_demo.py --auto-approve "Find the latest invoice from Nimbus Traders, extract the amount and due date, enter it into our internal system, and tell me once it is done."
```

Optional: set `ANTHROPIC_API_KEY` in your environment and `pip install anthropic`
to let the task-parsing step use Claude instead of the built-in regex fallback.
Nothing else changes -- this is a drop-in swap, not a different code path for the
rest of the agent.

Try the Nimbus Traders task first -- it's the one that exercises the failure/retry/
approval logic, since `invoice_102.txt` (the newest Nimbus invoice) is deliberately
missing its amount. The Bluepeak task shows the clean/generalization path on a
different company with no hand-written special-casing.

## Architecture, in one paragraph

`run_demo.py` just parses CLI args and prints the result. `worker.py` is the actual
loop: it calls `reasoner.parse_task()` once to figure out the target company, then
repeatedly calls into `tools.py` (list invoices, read, extract, write, verify) and
makes a decision after each call based on what came back -- continue, retry, fall
back to an older invoice, ask for human approval, or stop and explain why. `memory.py`
is just a dict + a list that lives for one run, holding facts the agent has learned
(e.g. "the invoice I ended up using") and the full step trace used for the final
report and the log file.

## Key design decisions

- **Tools are a small, closed set, not "give the model a shell."** The agent can
  only do what `tools.py` exposes (list/read/extract/write/verify). This is an
  intentional scope limit, not a corner cut -- it makes behavior predictable and
  reviewable, and matches "you do not need to support every website or workflow."
- **Reasoning is a thin, swappable layer, not the whole system.** `reasoner.py` only
  does one job (figure out which company the task means). If `ANTHROPIC_API_KEY`
  is set it asks Claude; otherwise it uses a regex that handles the same sentence
  shapes the brief itself uses as examples. Both return the same shape, so `worker.py`
  doesn't know or care which one ran. This keeps the demo runnable with zero secrets
  while leaving an obvious place to plug in real LLM reasoning for messier tasks.
- **The agent is written to expect failure, not to assume success.** Every tool call
  returns `{"ok": ..., ...}` and the loop checks it -- a write isn't trusted until a
  separate `verify_entry()` read confirms it, and a missing field doesn't crash the
  script, it triggers the fallback/approval logic.
- **Human approval is a real pause, not a log line.** When the agent would have to
  substitute an older invoice for the one actually requested, it stops and asks
  (via a terminal prompt in this prototype) rather than silently making that call
  on its own.
- **A plain state machine instead of an agent framework.** At this scope, explicit
  `if/while` logic in `worker.py` is easier to read, debug, and explain than wiring
  up a generic executor would be -- there just isn't enough branching yet to need one.

## Known limitations

- Task understanding is narrow: it currently extracts *one* thing (the target company)
  from the sentence. It doesn't yet parse arbitrary multi-step instructions or handle
  tasks that don't fit the "find an invoice and log it" shape.
- Invoice parsing is regex/label-based, tuned to the fixed `Label: value` format used
  here. A real invoice (PDF, scanned, inconsistent layout) would need a different
  extraction step (e.g. an LLM call or OCR), which the brief explicitly says is fine
  to mock/limit for a prototype.
- The "internal system" is a single JSON file with no concurrency handling -- fine
  for a single-agent demo, not for multiple agents writing at once.
- Human approval is a blocking terminal prompt. A real system would probably surface
  this as a notification/ticket the person can answer asynchronously.
- No persistent memory across separate runs -- each run starts fresh. Only within a
  single run does the agent carry state between steps.

## What I'd build next with more time

- A second, genuinely different tool (e.g. a tiny simulated web form via a headless
  browser) to test generalization across *kinds* of tools, not just across inputs
  to the same tool.
- Replace the regex extractor with an LLM-based one behind the same `extract_fields()`
  interface, so messier/unstructured invoices work without changing `worker.py`.
- A lightweight eval harness: a set of task + expected-outcome pairs run automatically
  against the agent to catch regressions, instead of manually re-running scenarios.
- Persist memory (e.g. "I've already processed invoice X") across runs, not just
  within one, so re-running the same task repeatedly is cheap and safe by default
  rather than relying on the internal-system idempotency check alone.

## Assumptions made

- "Latest invoice" means most recent `Date Issued`, not file modification time.
- A task always names the company close to literally (e.g. "from Nimbus Traders"),
  matched case-insensitively against the `Company:` field in the invoice.
- "Enter it into our internal system" means append a record if one doesn't already
  exist for that invoice number; re-running an already-completed task is treated as
  success, not an error.

## Models / APIs / frameworks used

- Python 3 standard library only for the core agent loop, tools, and mock environment.
- Optional: the `anthropic` Python SDK + `claude-sonnet-5`, used only in
  `reasoner.py` for parsing the task sentence, and only if `ANTHROPIC_API_KEY` is set.
  No other external services, frameworks, or pre-built agent libraries are used --
  this was built as plain, explicit code on purpose, to keep it fully inspectable.
