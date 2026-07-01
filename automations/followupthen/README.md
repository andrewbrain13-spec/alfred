# Automation #3 — FollowUpThen: draft a nudge when there's no real reply

**Trigger:** a FollowUpThen reminder email (`followupthen.com` / `fut.io`),
typically at 6 AM CST.
**Action:** find the original thread, check whether an **external** party has
sent a **meaningful** reply since you last wrote; if not, create a **draft**
reply ("Any update on this?") addressed to that party, **BCC** the FollowUpThen
weekday address so a new reminder is scheduled when you send.

**It only ever creates a draft — it never sends.** You review it in Outlook
Drafts and click Send. That way, if you already resolved it by phone or in
another thread, you just delete the draft.

## Reschedule timing
+3 days, snapped forward to a weekday, expressed as the weekday name:

| Reminder day | BCC |
| --- | --- |
| Monday | `thursday@fut.io` |
| Tuesday | `friday@fut.io` |
| Wednesday | `monday@fut.io` (Sat→Mon) |
| Thursday | `monday@fut.io` (Sun→Mon) |
| Friday | `monday@fut.io` |

Change the interval in `fut_common.weekday_bcc` (default `days=3`).

## "Meaningful external reply" judgment
A Claude call decides. It counts as meaningful only if it's a substantive reply
from an external participant (not `braingroup.com`) **after** your last outbound.
It excludes internal-only discussion, auto-replies/OOO, and bare acknowledgements.
Adjust internal domains via `FUT_INTERNAL_DOMAINS`.

## Going live
1. Leave `ALFRED_DRY_RUN: "1"` — it logs the thread it found, the judgment, and
   the draft it *would* create.
2. Run `python run.py --config config/rules.yaml --once` after a real reminder;
   read the output.
3. Set `ALFRED_DRY_RUN: "0"` to have it create the draft (still safe — you send).

## To finalize
- Send me a sample **FollowUpThen reminder** email so I can confirm the sender
  address and that subject-based thread lookup finds the right conversation
  (some FUT setups reply within the thread; others send a fresh email).
- Confirm the nudge wording / whether you want it to alternate between "Any
  update on this?" and "Touching base on next steps."
