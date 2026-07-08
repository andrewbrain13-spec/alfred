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
   session normally already exists, so it lands in the **manager portal** — in
   that case **do not log in** and skip to step 2.
   - Only if you are sent to a sign-in page: log in via PrismONE ID — open
     `https://lvr-ep.prismhr.com/uex/#/auth/login`, click **"Sign In with
     PrismONE ID"**, and enter `PRISM_USERNAME` / `PRISM_PASSWORD`. For the
     authenticator code run `.venv/Scripts/python.exe automations/prism/totp.py`
     and enter its output. Then reopen the deep link.
2. Click **Approvals** in the top-right corner.
3. Find the pending Leave request for the **employee named in the email**.
4. Confirm the dates line up: the individual dates in the email should fall
   within the request's leave dates shown in the queue (the queue may show
   **ranges** like `12/16 – 12/18` — expand them; the email may list each day
   separately). They describe the same time off.
5. If that employee has **exactly one** pending leave request and the dates are
   consistent, click the **approve checkmark** for that request.
6. Do not deny, edit, or approve any other request.

## Safety rules
- Approve **exactly one** request — the one this email is about.
- If you find **zero** matching requests, or **more than one** pending request
  for that employee that you cannot disambiguate by dates, do NOT approve
  anything. Report what you saw and stop.
- If the employee's queue dates clearly conflict with the email (a different
  span entirely, not just range-vs-list formatting), do NOT approve.

## Handling secrets safely
- Prefer the existing logged-in session; the password should rarely be needed.
- If you must enter the password, read it from the `PRISM_PASSWORD` environment
  variable and type it **directly into the browser field**. Do NOT write it into
  any script, file, or command-line argument, do NOT copy it to the clipboard,
  and never echo or print it.

## Output
End with a short structured summary:
- EMPLOYEE: <name>
- DATES: <list>
- MATCHED_IN_QUEUE: yes/no
- ACTION_TAKEN: approved / dry-run-would-approve / skipped (reason)
