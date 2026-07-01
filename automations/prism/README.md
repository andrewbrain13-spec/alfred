# Automation #1 — Auto-approve Lever1/Prism leave requests

**Trigger:** a leave-approval email from your PEO, Lever1 (PrismHR).
**Action:** approve that request (unlimited-PTO policy → tracking only).

## Confirmed notification format (from a real sample)
- **Sender:** `support@lever1.com`
- **Subject:** `Leave approval needed for <Employee Name> (Brain Group)`
- **Body:** names the employee, each `MM/DD/YYYY (N.NN Hours)` entry, the plan
  (`UNLMTD`), and a **direct approval deep link**:
  `https://lvr.prismhr.com/lvr?a=ap&c=<id>&bkey=<token>`

The deep link (`a=ap` = approve action) points straight at this one request,
so the browser path opens it directly rather than searching a queue.

Two implementations are provided; pick one in `config/rules.yaml`. The browser
path (B) is recommended here since we have a working deep link.

## Path A — API (preferred, deterministic)

Uses the PrismHR Services API. Requires a **web service user** created by your
PrismHR administrator/PEO. Fill in the endpoint constants in
`prism_approve_api.py` from your instance's docs (https://api-docs.prismhr.com).

Rule:

```yaml
- name: "Prism PTO -> approve (API)"
  match:
    from: "support@lever1\\.com"
    subject: "(?i)leave approval needed"
  workflows:
    - type: run_command
      command: ["python", "automations/prism/prism_approve_api.py"]
      env:
        PRISM_API_BASE: ${PRISM_API_BASE}
        PRISM_API_TOKEN: ${PRISM_API_TOKEN}
        ALFRED_DRY_RUN: "1"               # "0" to actually approve
```

## Path B — Browser (no API access)

Claude Code drives a headless browser (Playwright MCP) to log in and approve.
Credentials come from environment variables; the task lives in
`approve_task.md`.

Rule:

```yaml
- name: "Prism PTO -> approve (browser)"
  match:
    from: "support@lever1\\.com"
    subject: "(?i)leave approval needed"
  workflows:
    - type: claude_agent
      task_file: automations/prism/approve_task.md
      mcp_config: mcp/playwright.json
      allowed_tools: ["mcp__playwright__*"]
      dry_run: true                       # false to go live
      output_to: prism_approvals.log
```

Set credentials as environment variables (used by the task via the browser):

```bat
setx PRISM_URL "https://your-tenant.prismhr.com/login"
setx PRISM_USERNAME "you@braingroup.com"
setx PRISM_PASSWORD "..."
```

## Going live safely

1. Leave `dry_run: true` / `ALFRED_DRY_RUN: "1"` at first.
2. Trigger a real (or forwarded) Prism notification and run
   `python run.py --config config/rules.yaml --once`.
3. Read `prism_approvals.log` (browser) or stdout (API) — confirm it identified
   the correct employee, dates, and request, and that its *would-approve* target
   is right.
4. Only then flip the flag to go live.

## Still to confirm before first run

- **Portal login / MFA** (Path B) — set `PRISM_URL`, `PRISM_USERNAME`,
  `PRISM_PASSWORD`. If the Lever1 portal login requires 2FA that can't be
  automated, we'll need an app password or an exempted service login; the task
  is written to stop and report rather than guess. (If the deep link opens the
  approval without a fresh login because a browser session persists, even
  simpler.)
- **API availability** (optional, Path A) — only if you'd rather not use the
  browser: ask Lever1 whether they can issue a PrismHR web service user.

Resolved from the sample email: sender (`support@lever1.com`), subject pattern,
body fields, and the direct approval deep link — all wired in.
