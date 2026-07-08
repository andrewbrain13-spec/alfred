# Task: approve a Lever1 / Prism leave request (browser)

You are approving a leave (PTO) request in the Lever1 Prism **manager** portal on
behalf of the account owner. The company (Brain Group) has an **unlimited PTO**
policy (Time Off Plan "UNLMTD"), so these requests are tracked, not rationed — a
valid request should be approved.

## The notification (from support@lever1.com)
Subject: `Leave approval needed for <Employee Name> (Brain Group)`
The email JSON (path given below) contains, in its body:
- the **employee name** (also in the subject, between "Leave approval needed for"
  and "(Brain Group)"),
- the **requested dates + hours** (`MM/DD/YYYY (N.NN Hours)` entries),
- a **deep link** of the form `https://lvr.prismhr.com/lvr?a=ap&c=...&bkey=...`.

Read these from the email JSON first.

## Steps
1. Open the **deep link** from the email with the Playwright browser. A logged-in
   session should already exist, so it lands in the **manager portal**.
   - If you are sent to a sign-in page instead, log in via PrismONE ID: open
     `https://lvr-ep.prismhr.com/uex/#/auth/login`, click **"Sign In with
     PrismONE ID"**, enter the email from `PRISM_USERNAME` and password from
     `PRISM_PASSWORD`, and for the authenticator code run
     `.venv/Scripts/python.exe automations/prism/totp.py` and enter its output.
     Read secrets only from environment variables; never print them. Then reopen
     the deep link.
2. Click **Approvals** in the top-right corner.
3. Find the pending request that matches the **employee name AND dates** from the
   email. Confirm both match before acting — never approve a request you cannot
   positively match.
4. Click the **approve checkmark** next to **that one** request.
5. Do not deny, edit, or approve any other request.

## Safety rules
- Approve **exactly one** request — the one this email is about.
- If you find zero matching requests, or more than one plausible match, do NOT
  approve anything. Report what you saw and stop.
- If the employee/dates in the queue do not match the email, do NOT approve.

## Output
End with a short structured summary:
- EMPLOYEE: <name>
- DATES: <list>
- MATCHED_IN_QUEUE: yes/no
- ACTION_TAKEN: approved / dry-run-would-approve / skipped (reason)
