@echo off
REM Keep the Prism login session fresh so headless approvals never hit an
REM expired session. Schedule this to run every couple of days (e.g. every 2
REM days at 00:00) via Task Scheduler. Logs to prism_keepalive.log.
cd /d C:\Alfred
.venv\Scripts\python.exe automations\prism\login.py >> prism_keepalive.log 2>&1
