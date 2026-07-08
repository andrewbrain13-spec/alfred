# Task: approve a Lever1 / Prism leave request (browser)

You are approving a leave (PTO) request in the Lever1 Prism **manager** portal on
behalf of the account owner. The company (Brain Group) has an **unlimited PTO**
policy, so these requests are tracked, not rationed — a valid request should be
approved.

A logged-in session is **pre-loaded** into the browser, so you should already be
authenticated. **Do not attempt to log in and never handle any password.** If you
find yourself on a sign-in page, the session has expired — STOP and report
`RESULT: SESSION_EXPIRED` so the login script can refresh it. Do not enter
credentials.

## The notification (from support@lever1.com)
The email JSON (path given below) contains, in its body:
- the **employee name** (also in the subject, between "Leave approval needed for"
  and "(Brain Group)"),
- the **requested dates + hours** (`MM/DD/YYYY (N.NN Hours)` entries),
- a **deep link** of the form `https://lvr.prismhr.com/lvr?a=ap&c=...&bkey=...`.

Read these from the email JSON first.

## Steps
1. Open the **deep link** from the email — it lands in the manager portal. (If it
   shows a sign-in page, STOP and report `RESULT: SESSION_EXPIRED`.)
2. Click **Approvals** in the top-right corner.
3. Find the pending Leave request for the **employee named in the email**.
4. Confirm the dates line up: the individual dates in the email should fall within
   the request's leave dates in the queue (the queue may show **ranges** like
   `12/16 – 12/18`; expand them — the email may list each day separately). They
   describe the same time off.
5. If that employee has **exactly one** pending leave request and the dates are
   consistent, click the **approve checkmark** for that request.
6. Do not deny, edit, or approve any other request.

## Safety rules
- Approve **exactly one** request — the one this email is about.
- If you find **zero** matching requests, or **more than one** pending request for
  that employee you cannot disambiguate by dates, do NOT approve. Report and stop.
- If the employee's queue dates clearly conflict with the email, do NOT approve.

## Output (last line matters — Alfred keys off it)
End with a structured summary, and make the final line EXACTLY one of:
- `RESULT: APPROVED` — you clicked the approve checkmark for the matching request.
- `RESULT: SKIPPED` — nothing approved (no match / ambiguous / mismatch). Explain above.
- `RESULT: SESSION_EXPIRED` — you hit a sign-in page.

Also include: EMPLOYEE, DATES, and MATCHED_IN_QUEUE (yes/no).
