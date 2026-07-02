# Automation #2 — Piper NLC/RLC checklist → OneDrive tracker

**Trigger:** Piper emails an NLC (New Lease Checklist) or RLC (Renewal Lease
Checklist) share link to the distribution list.
**Action:** append a row to **Table1** in `NLC tracking.xlsx` on OneDrive, with
the **share link** in the Link column.

## The tracking table
`NLC tracking.xlsx` → `Sheet1` → `Table1`, columns A..J:

| Tenant | date | N/R/T | Kimmy | John | Ashley | Tracy | Dawn | Darrell | Link |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

The automation fills **Tenant**, **date** (today), **N/R/T** (`N` for new, `R`
for renewal), and **Link**. The per-person columns are left blank for you to
mark with `X`.

### Filing the email
After logging, the email is marked **read** and moved to the **building's**
subfolder under `Inbox/portfolio`. The building is read from the email text
(e.g. "New Tenant at Foxridge!" → the `Foxridge` folder) by matching a folder
name as a whole token-phrase in the subject/body. If no building is confidently
matched, the email is marked read and left in the inbox, and the available
folder names are logged.

For emails that don't state the building (e.g. some renewals), add an override
in `automations/piper/folder_map.json` mapping the tenant to the building
folder:

```json
{ "SIRO": "39th Street", "Mission Kitchen & Bath": "Foxridge" }
```

Configure the parent folder name with `PIPER_PORTFOLIO_FOLDER` (default
`portfolio`).

Rows are added via the Graph Excel API
(`/workbook/tables/Table1/rows`), which extends the table correctly. Path and
table name are configurable via `PIPER_TRACKING_PATH` / `PIPER_TABLE`.

## Going live
1. Leave `ALFRED_DRY_RUN: "1"` — it prints the row it *would* add (tenant, date,
   type, link) so you can confirm the parse.
2. Run `python run.py --config config/rules.yaml --once` after a real Piper
   email; check the parsed values.
3. Set `ALFRED_DRY_RUN: "0"` to write rows for real.

## To finalize (need a sample Piper email)
Extraction is best-effort until I see a real one. Please share a Piper checklist
email so I can confirm:
- the **sender address** (to add to the rule's `from` and avoid false matches),
- the **subject/body wording** (to reliably pull the **tenant** name and N vs R),
- the exact **share-link** format (SharePoint `-my.sharepoint.com`, `1drv.ms`,
  a `/:x:/` link, etc.) so `_LINK_RE` grabs the right URL.
