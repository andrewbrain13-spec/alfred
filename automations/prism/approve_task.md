# Task: approve a Prism time-off request (browser)

You are automating an approval in the Prism (PrismHR) web portal on behalf of
the account owner. The company has an **unlimited PTO** policy, so time-off
requests are tracked, not rationed — a valid request should be approved.

## Context
A notification email was received indicating an employee submitted a time-off
request. The email is provided to you as JSON (path given below); it contains
the sender, subject, and body. Extract from it:
- the employee's name,
- the requested dates / date range,
- any request identifier or direct link Prism included.

## Steps
1. Open the Prism portal login page (URL from the `PRISM_URL` environment
   variable) using the browser tools.
2. Log in with the credentials in the `PRISM_USERNAME` and `PRISM_PASSWORD`
   environment variables. If an MFA/2FA prompt appears that you cannot satisfy
   automatically, STOP and report that manual login is required — do not guess.
3. Navigate to the pending time-off / PTO approvals queue.
4. Locate the request that matches the employee and dates from the email. If a
   direct link was in the email, use it. Confirm the name AND the dates match
   before acting — never approve a request you cannot positively match.
5. Approve **only** that one request.
6. Do not deny, edit, or approve any other request.

## Safety rules
- If you find zero matching requests, or MORE THAN ONE plausible match, do NOT
  approve anything. Report what you saw and stop.
- If the dates or employee in the queue do not match the email, do NOT approve.
- Report exactly what you did (or would do), including the employee, the dates,
  and the request ID, so there is an audit trail.

## Output
End with a short structured summary:
- MATCHED: yes/no
- EMPLOYEE, DATES, REQUEST_ID
- ACTION_TAKEN: approved / dry-run-would-approve / skipped (reason)
