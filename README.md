# Autonomous AI Task Worker

A lightweight prototype of an autonomous AI worker that accepts a natural-language task, reasons about what needs to be done, executes a sequence of controlled tools, handles failures, requests human approval when necessary, verifies its actions, and produces an execution report.

The prototype focuses on a narrow but complete workflow:

> "Find the latest invoice from Nimbus Traders, extract the amount and due date, enter it into our internal system, and tell me once it is done."

Instead of interacting with real third-party systems, the project uses a local mock company environment. This keeps the system safe, reproducible, and easy to run.

---

##  What This Project Demonstrates

The worker follows a simple:

**Plan → Act → Observe → Recover → Verify → Report**

workflow.

Given a natural-language task, it can:

1. Identify the target company from the task.
2. Search available invoices.
3. Determine the latest invoice based on the issue date.
4. Extract the invoice number, amount, and due date.
5. Detect malformed or incomplete invoice data.
6. Fall back to the next valid invoice when necessary.
7. Request human approval before making a potentially unsafe substitution.
8. Write the processed invoice into a simulated internal system.
9. Verify that the write operation actually succeeded.
10. Produce a human-readable execution summary.
11. Maintain a detailed execution trace for debugging and auditing.

The important part is that the worker does not simply assume that every action succeeds.

---

#  Architecture

```text
                    Natural Language Task
                            │
                            ▼
                    ┌───────────────┐
                    │   Reasoner    │
                    │               │
                    │ Identify      │
                    │ target company│
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    Worker     │
                    │               │
                    │ Plan          │
                    │ Act           │
                    │ Observe       │
                    │ Recover       │
                    │ Verify        │
                    │ Report       │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
        ┌──────────┐  ┌───────────┐  ┌──────────┐
        │  Read    │  │  Extract  │  │  Write   │
        │ Invoices │  │  Fields   │  │  System  │
        └──────────┘  └───────────┘  └────┬─────┘
                                          │
                                          ▼
                                    ┌───────────┐
                                    │  Verify   │
                                    │  Result   │
                                    └─────┬─────┘
                                          │
                                          ▼
                                    Final Report
````

---

#  Project Structure

```text
autonomous-ai-worker/
│
├── agent/
│   ├── __init__.py
│   ├── memory.py
│   ├── reasoner.py
│   ├── tools.py
│   └── worker.py
│
├── mock_company_app/
│   ├── invoices/
│   │   ├── invoice_101.txt
│   │   ├── invoice_102.txt
│   │   └── invoice_201.txt
│   │
│   └── internal_system.json
│
├── logs/
│   └── run_log.jsonl
│
├── README.md
├── requirements.txt
└── run_demo.py
```

### Core Components

| Component                               | Responsibility                                     |
| --------------------------------------- | -------------------------------------------------- |
| `run_demo.py`                           | CLI entry point                                    |
| `agent/worker.py`                       | Main agent execution loop                          |
| `agent/reasoner.py`                     | Converts natural language into a structured target |
| `agent/tools.py`                        | Controlled actions available to the agent          |
| `agent/memory.py`                       | Maintains state and execution history              |
| `mock_company_app/invoices/`            | Simulated invoice repository                       |
| `mock_company_app/internal_system.json` | Simulated accounting/internal system               |
| `logs/run_log.jsonl`                    | Execution and audit history                        |

---

#  Execution Flow

## 1. Task Understanding

The worker receives a natural-language instruction:

```text
Find the latest invoice from Nimbus Traders,
extract the amount and due date,
enter it into our internal system.
```

The reasoning layer identifies:

```text
Target company: Nimbus Traders
Requested action: Process latest invoice
```

The reasoning layer is intentionally isolated from the rest of the system.

---

## 2. Invoice Discovery

The worker searches the invoice directory and identifies invoices belonging to the requested company.

For example:

```text
invoice_101.txt → Nimbus Traders → valid
invoice_102.txt → Nimbus Traders → invalid
invoice_201.txt → Bluepeak Solutions → valid
```

The worker determines the latest invoice using the:

```text
Date Issued
```

field rather than relying on file modification time.

---

## 3. Failure Detection

The newest Nimbus Traders invoice is intentionally malformed.

For example:

```text
Invoice Number: INV-102
Company: Nimbus Traders
Amount: <missing>
Due Date: invalid
```

Instead of crashing or silently continuing, the worker detects the invalid data.

---

## 4. Recovery + Human Approval

The worker searches for the next most recent valid invoice.

However, it does **not automatically substitute it**.

Instead, it asks for human approval:

```text
The latest invoice could not be processed.

A previous valid invoice was found:
INV-101

Would you like to use this invoice instead? [y/n]
```

This creates a human-in-the-loop safety boundary.

---

## 5. Write Operation

After approval, the worker writes the extracted information into:

```text
mock_company_app/internal_system.json
```

Example:

```json
{
  "invoice_number": "INV-101",
  "company": "Nimbus Traders",
  "amount": "INR 45,000",
  "due_date": "2026-10-10"
}
```

Before writing, the worker checks whether the invoice already exists.

This makes the operation idempotent.

---

## 6. Verification

The worker does not assume that a successful write means the operation actually succeeded.

It reads the record back from the internal system and verifies:

```text
Invoice exists
Company matches
Amount matches
Due date matches
```

Only after successful verification is the operation considered complete.

---

## 7. Final Report

The worker produces a human-readable result such as:

```text
SUCCESS

Invoice INV-101 for Nimbus Traders was entered successfully.

Amount: INR 45,000
Due date: 2026-10-10

Note:
The latest invoice could not be processed because required
fields were invalid. A previous valid invoice was used after
human approval.
```

---

#  Agent Design

The worker uses a lightweight state-machine approach rather than a generic agent framework.

The execution loop is conceptually:

```text
Task
  │
  ▼
Reason
  │
  ▼
Choose Action
  │
  ▼
Execute Tool
  │
  ▼
Observe Result
  │
  ├── Success ───────────────┐
  │                          │
  ├── Recoverable Failure ───┤
  │                          │
  ├── Approval Required ─────┤
  │                          │
  └── Fatal Failure ──► Stop │
                             ▼
                          Verify
                             │
                             ▼
                           Report
```

This approach keeps the behavior explicit and easy to debug.

---

#  Controlled Tool Interface

The agent does not receive unrestricted shell or filesystem access.

Instead, it can only use a small set of predefined operations exposed through `tools.py`.

Typical operations include:

```text
list_invoices()
read_invoice()
extract_fields()
write_entry()
verify_entry()
```

This provides a clear boundary between:

**Reasoning**

and

**Actions the agent is actually allowed to perform.**

This is especially useful when extending the prototype toward real-world agent systems.

---

#  Human-in-the-Loop Safety

Human approval is required when the worker wants to deviate from the original request.

Example:

```text
Requested:
Latest invoice

Found:
Latest invoice → invalid

Fallback:
Previous invoice → valid

Decision:
Ask human before substitution
```

This prevents the worker from silently making a potentially incorrect business decision.

---

#  Execution Logging

Every run produces a JSON Lines (`JSONL`) execution trace.

Example:

```json
{
  "success": true,
  "summary": "Invoice INV-101 processed successfully."
}
```

The execution trace makes it possible to inspect:

* What the worker attempted
* Which tools were called
* What each tool returned
* Where failures occurred
* Whether recovery was triggered
* Whether human approval was required
* Whether the final result was verified

This provides basic observability and auditability.

---

#  Getting Started

## Requirements

* Python 3.8+
* No external dependencies required for the core workflow

Clone the repository:

```bash
git clone https://github.com/<your-username>/autonomous-ai-worker.git
cd autonomous-ai-worker
```

Run the default demo:

```bash
python run_demo.py
```

---

#  Running Custom Tasks

You can provide your own task:

```bash
python run_demo.py "Find the latest invoice from Bluepeak Solutions and enter it into our internal system."
```

For an unattended demo:

```bash
python run_demo.py --auto-approve "Find the latest invoice from Nimbus Traders, extract the amount and due date, enter it into our internal system, and tell me once it is done."
```

---

#  Demo Scenarios

## Scenario 1 — Successful Execution

```text
Bluepeak Solutions
        ↓
Latest valid invoice
        ↓
Extract fields
        ↓
Write to internal system
        ↓
Verify
        ↓
SUCCESS
```

This demonstrates the normal execution path.

---

## Scenario 2 — Failure + Recovery

```text
Nimbus Traders
        ↓
Latest invoice
        ↓
Invalid data
        ↓
Find previous valid invoice
        ↓
Human approval
        ↓
Write
        ↓
Verify
        ↓
SUCCESS
```

This demonstrates failure handling and human-in-the-loop decision making.

---

## Scenario 3 — Duplicate Request

If the same invoice has already been processed:

```text
Invoice already exists
        ↓
No duplicate write
        ↓
Verify existing record
        ↓
SUCCESS
```

This demonstrates idempotent behavior.

---

#  Safety & Scope

This prototype intentionally operates inside a local mock environment.

It does **not**:

* Access real accounting systems
* Use real customer credentials
* Modify third-party websites
* Execute arbitrary shell commands
* Access unrestricted files
* Perform financial transactions
* Make irreversible external changes

The restricted environment makes the behavior deterministic and safe to experiment with.

---

#  Optional LLM Reasoning

The core system works without an LLM.

By default, `reasoner.py` uses a lightweight parsing strategy.

An LLM can optionally be introduced as the reasoning layer while keeping the rest of the architecture unchanged.

Conceptually:

```text
Natural Language
       │
       ▼
┌───────────────────┐
│ Reasoning Layer   │
│                   │
│ Regex / LLM       │
└─────────┬─────────┘
          │
          ▼
Structured Task
          │
          ▼
       Worker
```

This separation means the reasoning implementation can evolve without rewriting the worker or tool layer.

---

#  Current Limitations

This is intentionally a prototype and has several limitations.

### Task Understanding

The current reasoner primarily identifies the target company.

It does not yet support arbitrary multi-step natural-language workflows.

### Invoice Extraction

Invoice parsing currently relies on predictable text labels.

Real-world invoices may require:

* OCR
* PDF parsing
* Vision models
* LLM-based extraction
* Schema validation

### Internal System

The internal system is represented by a JSON file.

It does not provide:

* Concurrent writes
* Authentication
* Transactions
* Access control
* Distributed state

### Human Approval

Approval currently happens through the terminal.

A production implementation could use:

* Web UI
* Slack
* Email
* Approval dashboard
* Task queue

### Memory

Working memory currently exists only during a single execution.

Persistent memory across runs is not implemented yet.

---

# 🔮 Future Improvements

Potential next steps include:

### 1. Real Tool Integration

Add a second tool type such as a simulated web form or browser-based workflow.

### 2. LLM-Based Extraction

Replace regex-based invoice extraction with an LLM/OCR pipeline while keeping the same tool interface.

### 3. Persistent Agent Memory

Store information such as:

```text
Previously processed:
INV-101
INV-201
```

to reduce repeated work across executions.

### 4. Evaluation Framework

Create automated test cases:

```text
Task → Expected Outcome
```

and run them automatically to measure:

* Task success rate
* Recovery success rate
* Tool errors
* Verification failures
* Human approval frequency

### 5. Production-Ready Internal System

Replace the JSON mock system with an API/database layer supporting:

* Authentication
* Transactions
* Concurrency
* Audit logs
* Role-based access control

---

#  Design Philosophy

The project follows a few core principles:

### Explicit over magical

The worker uses a simple state machine instead of hiding execution inside a large agent framework.

### Tools over unrestricted access

The agent gets a small set of explicitly defined capabilities rather than unrestricted computer access.

### Failure-aware execution

Tool calls are treated as potentially unreliable.

### Verify instead of assume

Important actions are verified independently after execution.

### Human approval for ambiguity

When the system needs to make a decision outside the original request, it asks a human instead of silently guessing.

### Replaceable reasoning

The reasoning layer can be replaced without rewriting the execution engine.

---

#  Key Takeaway

This project demonstrates a small but complete autonomous-worker architecture:

```text
Natural Language Task
        ↓
    Reasoning
        ↓
    Planning
        ↓
  Tool Execution
        ↓
    Observation
        ↓
 Failure Recovery
        ↓
 Human Approval
        ↓
     Action
        ↓
   Verification
        ↓
      Report
```

The goal is not to build a general-purpose AI agent.

The goal is to demonstrate how an AI worker can perform a **realistic, constrained workflow reliably**, while remaining observable, recoverable, and safe.

---
