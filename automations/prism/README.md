# Automation #1 — Auto-approve Prism time-off requests

**Trigger:** a Prism (PrismHR) notification email saying an employee requested
time off.
**Action:** approve that request (unlimited-PTO policy → tracking only).

Two implementations are provided; pick one in `config/rules.yaml`.

## Path A — API (preferred, deterministic)

Uses the PrismHR Services API. Requires a **web service user** created by your
PrismHR administrator/PEO. Fill in the endpoint constants in
`prism_approve_api.py` from your instance's docs (https://api-docs.prismhr.com).

Rule:

```yaml
- name: "Prism PTO -> approve (API)"
  match:
    from: "@.*prismhr\\.com|prism"      # tighten to the real notification sender
    subject: "(?i)time off|pto|leave request"
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
    from: "@.*prismhr\\.com|prism"
    subject: "(?i)time off|pto|leave request"
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

## Known unknowns to confirm before first run

- **Sender/subject of the real Prism notification** — the `match` above is a
  guess; tighten it once you have a sample email.
- **API availability** — confirm with your PrismHR provider whether a web
  service user can be issued (Path A) or whether we use Path B.
- **MFA on the portal** (Path B) — if login requires 2FA that can't be
  automated, the browser path needs an app password or an exempted service
  account; the task is written to stop and report rather than guess.
