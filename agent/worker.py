"""
The main agent loop.

This is the part that actually does the "autonomous task worker" job
described in the brief: take a natural-language task, break it into
steps, use tools, observe what happens, recover from failure where it
reasonably can, ask a human when it can't, verify the outcome, and
report back.

The loop is written as plain, explicit Python (not a framework) on
purpose -- for a prototype at this scope, a readable state machine is
easier to build correctly, easier to debug, and easier to explain in a
review than a generic "agent executor" would be.
"""

import os

from agent import tools
from agent.memory import WorkingMemory
from agent.reasoner import parse_task


def run_task(task_text, auto_approve=False):
    memory = WorkingMemory()
    report_lines = []

    # --- 1. Understand the goal -----------------------------------------
    plan = parse_task(task_text)
    company = plan["company"]
    memory.remember("task", task_text)
    memory.remember("target_company", company)
    memory.log_step("parse_task", task_text, plan)

    if not company:
        msg = "Could not figure out which company this task refers to. Stopping and asking for clarification."
        memory.log_step("parse_task_failed", task_text, msg)
        return _finish(memory, success=False, summary=msg)

    # --- 2. Find the latest matching invoice -----------------------------
    invoices = tools.list_invoices()
    matches = [inv for inv in invoices if inv["company"].lower() == company.lower()]
    memory.log_step("list_invoices", {"company": company}, matches)

    if not matches:
        msg = f"No invoices found for '{company}'. Stopping and asking for clarification."
        memory.log_step("no_matches", company, msg)
        return _finish(memory, success=False, summary=msg)

    matches.sort(key=lambda inv: inv["date_issued"], reverse=True)
    candidates = list(matches)  # we may have to fall back to an older one

    chosen = None
    extracted = None
    skipped = []

    # --- 3. Try to read + extract the latest invoice, falling back if it's broken ---
    while candidates:
        current = candidates.pop(0)
        text = tools.read_invoice(current["path"])
        memory.log_step("read_invoice", current["filename"], "read ok")

        result = tools.extract_fields(text)
        memory.log_step("extract_fields", current["filename"], result)

        if result["ok"]:
            chosen = current
            extracted = result["fields"]
            break
        else:
            skipped.append({"filename": current["filename"], "missing": result["missing"]})
            memory.remember("last_extraction_issue", result["missing"])

    if not chosen:
        msg = (
            f"Found {len(matches)} invoice(s) for '{company}', but all of them were missing "
            f"required fields ({skipped}). Cannot safely proceed without a human check."
        )
        memory.log_step("extraction_exhausted", skipped, msg)
        return _finish(memory, success=False, summary=msg)

    if skipped:
        # We had to skip at least one broken invoice. Per the brief, this is exactly the
        # moment to ask for approval before silently using an older invoice instead of
        # the one the user actually asked for ("the latest").
        approved = _ask_approval(
            f"The latest invoice for '{company}' ({skipped[-1]['filename']}) is missing "
            f"{skipped[-1]['missing']}. Proceeding instead with the next most recent valid "
            f"invoice, {chosen['filename']} ({extracted.get('due_date')}). OK to continue?",
            auto_approve=auto_approve,
        )
        memory.log_step("ask_approval", "use older valid invoice instead of broken latest one", approved)
        if not approved:
            msg = "User did not approve falling back to an older invoice. Stopping."
            return _finish(memory, success=False, summary=msg)

    memory.remember("chosen_invoice", chosen["filename"])
    memory.remember("extracted_fields", extracted)

    # --- 4. Write to the internal system, with one retry on failure -----
    entry = {
        "invoice_number": extracted["invoice_number"],
        "company": extracted["company"],
        "amount": extracted["amount"],
        "due_date": extracted["due_date"],
    }

    write_result = tools.write_to_system(entry)
    memory.log_step("write_to_system", entry, write_result)

    if not write_result["ok"] and "already exists" in write_result["reason"]:
        # Not actually a failure -- the task is already done. Treat as success.
        memory.log_step("already_done", write_result["reason"], "treating as already complete")
    elif not write_result["ok"]:
        # One retry: re-read the invoice and try again in case it was a transient issue.
        memory.log_step("retry_write", "retrying once after failed write", None)
        write_result = tools.write_to_system(entry)
        memory.log_step("write_to_system_retry", entry, write_result)
        if not write_result["ok"]:
            msg = f"Could not write entry to the internal system after retrying: {write_result['reason']}"
            return _finish(memory, success=False, summary=msg)

    # --- 5. Verify the outcome was actually achieved, not just attempted ---
    verification = tools.verify_entry(entry["invoice_number"])
    memory.log_step("verify_entry", entry["invoice_number"], verification)

    if not verification["ok"]:
        msg = "Write appeared to succeed, but the entry could not be verified in the system afterwards."
        return _finish(memory, success=False, summary=msg)

    # --- 6. Report ---------------------------------------------------------
    summary = (
        f"Done. Entered invoice {entry['invoice_number']} for {entry['company']} "
        f"(amount {entry['amount']}, due {entry['due_date']}) into the internal system, "
        f"and confirmed it's there."
    )
    if skipped:
        summary += f" Note: skipped a newer but incomplete invoice ({skipped[-1]['filename']}) with approval."

    return _finish(memory, success=True, summary=summary)


def _ask_approval(question, auto_approve=False):
    """Human-in-the-loop checkpoint. In an unattended/demo run (AUTO_APPROVE=1), auto-approves and logs it."""
    if auto_approve:
        return True
    print(f"\n[AGENT NEEDS APPROVAL] {question} (y/n): ", end="")
    answer = input().strip().lower()
    return answer in ("y", "yes")


def _finish(memory, success, summary):
    memory.remember("success", success)
    memory.remember("summary", summary)
    return {
        "success": success,
        "summary": summary,
        "trace": memory.steps,
        "facts": memory.facts,
    }
