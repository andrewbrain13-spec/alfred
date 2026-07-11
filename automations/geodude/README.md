# Automation #4 — Geodude daily email (folder-triggered)

**Trigger:** a new day's Geodude run lands in the daily-runs folder (not a fixed
time — it sends whenever the files appear).
**Action:** email the `Geodude_Summary_<date>.docx` as the body, with every file
in that day's batch attached, to the distribution list.

This one is **time/folder-driven, not email-driven**, so it isn't a `rules.yaml`
rule — it's a **periodic task** Alfred runs inside its normal loop (see the
`tasks:` block in the config). No separate Windows task needed.

## How it works
Every few minutes Alfred runs `send_daily.py`, which:
1. Groups files in the folder by their `YYYYMMDD` filename token.
2. For a batch it hasn't sent, waits until the `Geodude_Summary_*.docx` has been
   present for the **settle period** (default 10 min) so all files finish landing.
3. Sends: subject from the doc's Title (falls back to
   `EnergyNet Daily Royalty Screen — <date>`), body = the Summary doc converted
   to HTML, attachments = every file in that batch.
4. Records the batch so it never sends twice.

If the summary doc never appears for a day, nothing is sent.

## Config (env)
```
GEODUDE_FOLDER          folder to watch (defaults to the OneDrive daily-runs path)
GEODUDE_TO              default abrain@braingroup.com
GEODUDE_CC              default chad@chadsneed.com, jorscheln@braingroup.com
GEODUDE_SETTLE_SECONDS  wait after the summary appears (default 600)
GEODUDE_DRY_RUN         "1" = log only (default), "0" = actually send
```

## Requirements
Needs `python-docx` + `mammoth` (Word → HTML) and the Graph **Mail.Send** scope.
Because Mail.Send is a new scope, re-consent once (see the rollout steps) so the
cached token includes it — otherwise the background process would stall trying
to prompt for consent.

## Going live
1. Leave `GEODUDE_DRY_RUN: "1"` at first — the log shows exactly what it *would*
   send (subject, recipients, attachment count) without sending.
2. Once a real batch dry-runs correctly, set `GEODUDE_DRY_RUN: "0"`.
