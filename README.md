# Alfred

An always-on local service that watches an email inbox and runs **workflows**
when incoming mail matches your **triggers**. One process, many triggers, many
workflows — all declared in a single YAML file, so adding a new automation
never requires touching code.

```
   ┌──────────┐   new mail    ┌────────────┐   matches?   ┌────────────┐
   │  Mailbox │ ────────────▶ │  Rule table │ ───────────▶ │ Workflows   │
   │ (M365)   │   (poll)      │ (triggers)  │   yes        │ run_command │
   └──────────┘               └────────────┘              │ call_webhook│
                                                          │ send_reply  │
                                                          │ save_attach │
                                                          └────────────┘
```

## Why this instead of a scheduled cloud task

- **Durable & local**: runs on your always-on PC as a Windows Scheduled Task /
  service, survives reboots, and can execute local scripts and touch local files.
- **Firewall-friendly**: polls over outbound HTTPS/IMAP — no public endpoint to
  expose for inbound webhooks.
- **Pluggable**: triggers and actions live in `config/rules.yaml`. New
  automation = a few lines of YAML.

## Quick start

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip
cp config/rules.example.yaml config/rules.yaml      # then edit it
export ALFRED_EMAIL_PASSWORD='your-app-password'    # never put secrets in YAML

python run.py --config config/rules.yaml --check     # validate config
python run.py --config config/rules.yaml --once      # single pass (test it)
python run.py --config config/rules.yaml             # run forever (the daemon)
```

To keep it running on Windows, see **[install/install-windows.md](install/install-windows.md)**.

## Choosing a source (Microsoft 365)

| Source | Setup effort | When to use |
| ------ | ------------ | ----------- |
| **`imap`** | Low — host + app password | Your tenant still allows IMAP basic auth / app passwords. Fastest to try. |
| **`graph`** | Medium — one-time Entra app registration | Supported, future-proof, no IMAP dependency. Recommended if IMAP is blocked. See **[install/graph-setup.md](install/graph-setup.md)**. |

Switching sources is a config change, not a rewrite — the engine, rules, and
workflows are identical for both.

## Triggers (the `match` block)

Conditions are ANDed; text conditions are case-insensitive regex (a plain word
acts as a substring match):

| Key | Matches against |
| --- | --------------- |
| `subject` | the subject line |
| `from` | the sender address |
| `to` | any recipient |
| `body` | the plain-text body |
| `has_attachment` | `true`/`false` |

## Workflows (the `workflows` list)

| `type` | Does | Key options |
| ------ | ---- | ----------- |
| `run_command` | Runs a local script/command | `command`, `shell`, `cwd`, `env`, `timeout`, `pass_body_stdin` |
| `call_webhook` | POSTs to a URL / web API | `url`, `method`, `json`, `body`, `headers` |
| `send_reply` | Sends a notification / reply email (SMTP) | `to`, `subject`, `body`, `smtp_*` |
| `save_attachments` | Saves attachments / body to disk | `dir`, `pattern`, `save_body`, `overwrite` |

Strings in workflow options support `{subject}`, `{from}`, `{to}`, `{date}`,
`{body}`, `{uid}` placeholders. `run_command` also exports `ALFRED_SUBJECT`,
`ALFRED_FROM`, and `ALFRED_UID` as environment variables.

## Adding your own workflow type

Create a class in `alfred/workflows/` that subclasses `Workflow` and implements
`run(self, message)`, then register it in `alfred/workflows/__init__.py`'s
`REGISTRY`. It's immediately usable from YAML via its `type` key.

## Project layout

```
run.py                     entrypoint (--once / --check / daemon)
alfred/
  config.py                loads YAML, expands ${ENV} secrets
  rules.py                 trigger matching
  dispatcher.py            match -> run workflows (failures isolated)
  engine.py                poll loop + graceful shutdown
  state.py                 remembers processed messages (dedup)
  models.py                Message / Attachment
  sources/                 imap_source.py, graph_source.py (pluggable)
  workflows/               run_command, call_webhook, send_reply, save_attachments
config/rules.example.yaml  copy to rules.yaml and edit
install/                   Windows + Graph setup guides
tests/                     offline smoke tests (no mailbox needed)
```

## Notes on secrets & safety

- Secrets go in environment variables, referenced as `${VAR}` in the config;
  `config/rules.yaml`, logs, state, and token caches are git-ignored.
- Workflow failures are logged and isolated — one failing action never stops
  the others or the daemon.
- Every message is marked processed after handling, so a workflow can't be
  re-run on the same email across restarts.
