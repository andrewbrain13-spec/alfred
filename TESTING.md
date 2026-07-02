# Testing Alfred on your work PC

Everything below runs in **dry-run** — nothing gets approved, sent, or written
until you explicitly flip a flag. Work top to bottom.

## Prerequisite: the AI "brain" (Claude Code)

Automations **#1 (Prism)** and **#3 (FollowUpThen judgment)** invoke Claude Code
locally. Automation **#2 (Piper)** needs none of this — it's pure Graph.

Install Claude Code (PowerShell):
```powershell
irm https://claude.ai/install.ps1 | iex
```
Also install Git for Windows (https://git-scm.com/downloads/win) so Claude Code's
Bash tool works — the Prism automation uses it to fetch the MFA code.

Authenticate with your **Claude Pro/Max subscription** (no API key needed):
```powershell
claude --version
claude          # opens a browser to log in; the login is then cached
```
Leaving yourself logged in is what lets the unattended automations run.

## 0. One-time setup

```bat
git clone <this repo> C:\Alfred
cd C:\Alfred
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy config\rules.example.yaml config\rules.yaml
```

### Register the Graph app (once)
Follow `install\graph-setup.md` (delegated / device-code). Then set:

```bat
setx ALFRED_TENANT_ID  "your-tenant-id"
setx ALFRED_CLIENT_ID  "your-client-id"
```

Close and reopen the terminal so `setx` values load. First run will print a
URL + code to sign in once; the token is then cached.

### Validate config
```bat
.venv\Scripts\python run.py --config config\rules.yaml --check
```
Expect: `Config OK: 3 rule(s), source 'graph'.`

## 1. Do a single dry-run pass

```bat
.venv\Scripts\python run.py --config config\rules.yaml --once
```

This checks your inbox once and runs any matching rule in dry-run. What each
automation prints:

- **Prism** → to `prism_approvals.log`: the employee, dates, and the request it
  *would* approve.
- **Piper** → to the console/log: the row it *would* add (tenant, date, N/R, link).
- **FollowUpThen** → to the console/log: the thread it found, the reply
  judgment, and the draft it *would* create (recipient + weekday BCC).

## Where are the logs?

- **`alfred.log`** in the repo folder (`C:\Alfred\alfred.log`) — everything the
  engine and workflows log. Set by `log_file:` in the config.
- **`prism_approvals.log`** — the Prism agent's transcript (its `output_to`).
- Console output — the same lines also print to the window when you run `--once`.

To watch the main log live in another terminal:
```powershell
Get-Content C:\Alfred\alfred.log -Wait
```

## 2. Test one automation at a time with a real email

The cleanest way to trigger on demand: forward a known sample to yourself (or
wait for a real one), then run `--once`. Because matching is by sender/subject,
forwarding usually still matches.

Send me the resulting `prism_approvals.log` / console output and I'll tighten
anything that's off.

## 3. Go live (per automation, only when its dry-run looks right)

In `config\rules.yaml`, for that automation:
- Prism: `dry_run: true` → `false`
- Piper: `ALFRED_DRY_RUN: "1"` → `"0"`
- FollowUpThen: `ALFRED_DRY_RUN: "1"` → `"0"` (still only creates a draft you send)

## 4. Run it always-on

Once you trust it, set it up as a Scheduled Task per
`install\install-windows.md` so it runs on boot and restarts on failure.

## Per-automation environment variables

```bat
:: Prism (browser path) — see automations\prism\README.md
setx PRISM_URL          "https://lvr.prismhr.com/lvr"
setx PRISM_USERNAME     "you@braingroup.com"
setx PRISM_PASSWORD     "..."
setx PRISM_TOTP_SECRET  "JBSWY3DPEHPK3PXP..."

:: Piper / FollowUpThen use Graph creds (ALFRED_TENANT_ID / ALFRED_CLIENT_ID)
:: plus the per-rule env already in config\rules.yaml.
```
