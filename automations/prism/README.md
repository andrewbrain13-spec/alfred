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

## MFA (one-time passcodes)

The Lever1 portal uses TOTP one-time passcodes. Rather than granting access to
your 1Password, enroll a **separate authenticator entry** for this PC and store
its secret in `PRISM_TOTP_SECRET`; Alfred generates codes on demand via
`automations/prism/totp.py`. Full steps are in the header of that file. In
short: when re-adding MFA in Prism, choose "enter code manually" to reveal the
base32 secret, add it to 1Password AND `setx PRISM_TOTP_SECRET "..."`.

Set these environment variables for the browser path:

```bat
setx PRISM_URL "https://lvr.prismhr.com/lvr"
setx PRISM_USERNAME "you@braingroup.com"
setx PRISM_PASSWORD "..."
setx PRISM_TOTP_SECRET "JBSWY3DPEHPK3PXP..."
```

## Optional: API path

Only if you'd rather not use the browser — ask Lever1 whether they can issue a
PrismHR web service user, then fill in `prism_approve_api.py`.

Resolved from the sample email: sender (`support@lever1.com`), subject pattern,
body fields, and the direct approval deep link — all wired in.
