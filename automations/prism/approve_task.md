# Task: approve a Lever1 / Prism leave request (browser)

You are approving a leave (PTO) request in the Lever1 PrismHR portal on behalf
of the account owner. The company (Brain Group) has an **unlimited PTO** policy
(Time Off Plan "UNLMTD"), so these requests are tracked, not rationed — a valid
request should be approved.

## The notification format (from support@lever1.com)
Subject: `Leave approval needed for <Employee Name> (Brain Group)`
Body example:
> Please review (Approve/Deny) the pending Leave Approval for **Darrell O
> Hopkins** for 12/11/2026 (8.00 Hours) 12/14/2026 (8.00 Hours) ... Darrell O
> Hopkins is on Time Off Plan UNLMTD and has -80.00 hours available.
> https://lvr.prismhr.com/lvr?a=ap&c=272464&bkey=xOOe7EWH2lRSk1125720

The email JSON is at the path given below. Extract from it:
- **Employee name** — from the subject, the text between "Leave approval needed
  for " and " (Brain Group)"; cross-check against the name in the body.
- **Requested dates + hours** — the `MM/DD/YYYY (N.NN Hours)` entries in the body.
- **Approval link** — the `https://lvr.prismhr.com/lvr?a=ap&...&bkey=...` URL in
  the body. This is the direct deep link to this specific approval.

## Steps
1. Open the approval link from the email with the browser tools.
2. If prompted to log in, use the `PRISM_URL` login page and the `PRISM_USERNAME`
   / `PRISM_PASSWORD` environment variables. If an MFA/2FA prompt appears that
   you cannot satisfy automatically, STOP and report that manual login is
   required — do not guess.
3. On the approval page, **verify** the employee name and the dates shown match
   what you extracted from the email. This is the safety check.
4. If — and only if — they match, click **Approve**.
5. Do not Deny, edit, or touch any other request.

## Safety rules
- If the page does not load the expected request, or the employee/dates on the
  page do not match the email, do NOT approve. Report what you saw and stop.
- Approve exactly one request — the one this email is about.
- Never approve based on the email alone; always confirm against the loaded page.

## Output
End with a short structured summary:
- EMPLOYEE: <name>
- DATES: <list>
- LINK: <approval url>
- PAGE_MATCH: yes/no
- ACTION_TAKEN: approved / dry-run-would-approve / skipped (reason)
