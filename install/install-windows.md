# Running Alfred always-on on Windows

Goal: Alfred starts on boot, runs in the background under your account, and
restarts if it crashes — without a console window in your face.

## 1. Install Python and dependencies

1. Install Python 3.10+ from https://python.org (check "Add python.exe to PATH").
2. In a terminal, from the repo folder:

   ```bat
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

## 2. Create your config

```bat
copy config\rules.example.yaml config\rules.yaml
```

Edit `config\rules.yaml` for your triggers and workflows.

## 3. Set secrets as environment variables

Never put passwords in the YAML. Set them once at the user level:

```bat
setx ALFRED_EMAIL_PASSWORD "your-app-password"
setx TEAMS_WEBHOOK_URL "https://..."
```

(Close and reopen the terminal so `setx` values take effect.)

## 4. Validate the config

```bat
.venv\Scripts\python run.py --config config\rules.yaml --check
.venv\Scripts\python run.py --config config\rules.yaml --once
```

`--once` does a single pass so you can confirm a real email triggers the right
workflow before running the loop.

## 5. Run it always-on with Task Scheduler

Task Scheduler is the simplest durable option (no extra software).

1. Open **Task Scheduler** → **Create Task** (not "Basic Task").
2. **General** tab:
   - Name: `Alfred`
   - Select **Run whether user is logged on or not**.
   - Check **Run with highest privileges** only if a workflow needs it.
3. **Triggers** tab → **New** → Begin the task: **At startup**. Also add a
   trigger **At log on** for redundancy.
4. **Actions** tab → **New** → Start a program:
   - Program/script: `C:\path\to\alfred\.venv\Scripts\pythonw.exe`
     (use `pythonw.exe`, not `python.exe`, to avoid a console window)
   - Add arguments: `run.py --config config\rules.yaml`
   - Start in: `C:\path\to\alfred`
5. **Settings** tab:
   - Check **If the task fails, restart every** 1 minute, up to 3 times.
   - Uncheck **Stop the task if it runs longer than...** (it's meant to run forever).
6. Click OK; enter your Windows password when prompted (needed for "run whether
   logged on or not").

Alfred now starts on boot and relaunches if it dies. Check `alfred.log` in the
repo folder to see activity.

### Alternative: NSSM (run as a true Windows Service)

If you want it to appear under `services.msc` with proper service semantics,
use [NSSM](https://nssm.cc/):

```bat
nssm install Alfred "C:\path\to\alfred\.venv\Scripts\pythonw.exe" "run.py --config config\rules.yaml"
nssm set Alfred AppDirectory "C:\path\to\alfred"
nssm start Alfred
```

## Updating rules later

Edit `config\rules.yaml` and restart the task/service:

```bat
schtasks /End /TN Alfred && schtasks /Run /TN Alfred
```
