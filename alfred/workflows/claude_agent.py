"""Hand a matched message off to Claude Code running headless.

This is Alfred's "brain" workflow: for tasks that need judgment or multi-step
tool use (log into a portal and click approve; decide whether a thread got a
real reply and draft a response), Alfred detects the trigger and delegates the
actual work to Claude Code in headless/print mode on the same machine.

Config keys:

* ``task`` – the instruction prompt for Claude. Placeholders like ``{subject}``
  / ``{from}`` / ``{body}`` are substituted from the message.
* ``task_file`` – path to a file containing the task prompt (used when ``task``
  is not given; keeps long prompts out of the YAML). Placeholders still apply.
  Exactly one of ``task`` / ``task_file`` is required.
* ``claude_bin`` (default ``claude``) – path to the Claude Code CLI.
* ``mcp_config`` – path to an MCP servers JSON (e.g. Playwright for the browser,
  a Graph server for OneDrive/email). Passed via ``--mcp-config``.
* ``allowed_tools`` – list of tool names to allow non-interactively
  (``--allowedTools``). Required for unattended runs so Claude never blocks on
  a permission prompt.
* ``permission_mode`` – ``--permission-mode`` value (e.g. ``acceptEdits``).
* ``dangerously_skip_permissions`` (default false) – full autonomy. Only enable
  once you trust an automation; it lets Claude act without any prompt.
* ``dry_run`` (default true) – when true, Alfred appends an explicit instruction
  telling Claude to REPORT what it would do and take no irreversible action
  (no approvals, no sending mail). Flip to false to go live.
* ``cwd`` / ``add_dirs`` – working directory and extra readable dirs.
* ``append_system_prompt`` – extra system prompt text (``--append-system-prompt``).
* ``timeout`` – seconds before the run is killed (default 900).
* ``output_to`` – optional file to append the agent's transcript/result to.

The full normalized message is written as JSON to a temp file and its path is
passed to Claude, so the agent can read sender, body, and attachment metadata
without truncation. Key fields are also exported as ``ALFRED_*`` env vars.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile

from ..models import Message
from .base import Workflow

log = logging.getLogger("alfred.claude_agent")

_DRY_RUN_NOTICE = (
    "\n\n[DRY RUN] Do NOT take any irreversible action: do not approve, submit, "
    "send email, or modify any external system. Instead, describe precisely the "
    "action you WOULD take (including the exact request/record and why), then stop."
)


class ClaudeAgent(Workflow):
    def _message_context_file(self, message: Message, workdir: str) -> str:
        payload = {
            "uid": message.uid,
            "subject": message.subject,
            "from": message.from_addr,
            "to": message.to_addrs,
            "date": message.date.isoformat() if message.date else None,
            "body_text": message.body_text,
            "body_html": message.body_html,
            "attachments": [
                {"filename": a.filename, "content_type": a.content_type, "size": a.size}
                for a in message.attachments
            ],
        }
        path = os.path.join(workdir, "message.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return path

    def run(self, message: Message) -> None:
        task = self.spec.get("task")
        if not task and self.spec.get("task_file"):
            with open(self.spec["task_file"], "r", encoding="utf-8") as fh:
                task = fh.read()
        if not task:
            raise ValueError("claude_agent requires a 'task' or 'task_file'")

        dry_run = self.spec.get("dry_run", True)
        claude_bin = self.spec.get("claude_bin", "claude")
        timeout = int(self.spec.get("timeout", 900))

        workdir = tempfile.mkdtemp(prefix="alfred-agent-")
        context_path = self._message_context_file(message, workdir)
        # Run Claude in Alfred's working dir (the repo) so the task's relative
        # paths (scripts, configs) resolve; keep the message JSON as an absolute
        # path since it lives in the temp dir.
        run_cwd = self.spec.get("cwd") or os.getcwd()

        prompt = self.render(str(task), message)
        prompt += (
            f"\n\nThe triggering email is saved as JSON at: {context_path}\n"
            f"Subject: {message.subject}\nFrom: {message.from_addr}"
        )
        if dry_run:
            prompt += _DRY_RUN_NOTICE

        cmd = [claude_bin, "-p", prompt, "--output-format", "text"]
        if self.spec.get("mcp_config"):
            # Absolute so it resolves regardless of the subprocess cwd.
            cmd += ["--mcp-config", os.path.abspath(self.spec["mcp_config"])]
        allowed = self.spec.get("allowed_tools")
        if allowed:
            cmd += ["--allowedTools", ",".join(allowed)]
        if self.spec.get("permission_mode"):
            cmd += ["--permission-mode", self.spec["permission_mode"]]
        if self.spec.get("dangerously_skip_permissions"):
            # Non-interactive: tools can't prompt. Dry-run safety comes from the
            # prompt notice (do not take irreversible actions), not permissions.
            cmd += ["--dangerously-skip-permissions"]
        if self.spec.get("append_system_prompt"):
            cmd += ["--append-system-prompt", self.spec["append_system_prompt"]]
        for d in self.spec.get("add_dirs", []):
            cmd += ["--add-dir", d]

        env = dict(os.environ)
        env["ALFRED_SUBJECT"] = message.subject
        env["ALFRED_FROM"] = message.from_addr
        env["ALFRED_UID"] = message.uid
        env["ALFRED_MESSAGE_JSON"] = context_path
        env["ALFRED_DRY_RUN"] = "1" if dry_run else "0"

        log.info(
            "Invoking Claude Code (%s, dry_run=%s) for %s", claude_bin, dry_run, message.uid
        )
        result = subprocess.run(
            cmd,
            cwd=run_cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        transcript = result.stdout.strip()

        # Self-heal: if the agent reports a recoverable condition (e.g.
        # SESSION_EXPIRED), run a recovery command (e.g. refresh the login) and
        # retry the agent once.
        recover_on = self.spec.get("recover_on")
        recover_cmd = self.spec.get("recover_command")
        if (recover_on and recover_cmd and not dry_run
                and result.returncode == 0 and re.search(recover_on, transcript)):
            rc = list(recover_cmd)
            if rc and rc[0] in ("python", "python3"):
                rc[0] = sys.executable
            log.info("Agent hit %r; running recovery then retrying once (%s)",
                     recover_on, message.uid)
            try:
                subprocess.run(rc, cwd=run_cwd, env=env, capture_output=True,
                               text=True, timeout=300)
            except Exception as exc:
                log.warning("Recovery command failed (%s): %s", message.uid, exc)
            result = subprocess.run(cmd, cwd=run_cwd, env=env, capture_output=True,
                                    text=True, timeout=timeout)
            transcript = result.stdout.strip()

        if self.spec.get("output_to"):
            with open(self.spec["output_to"], "a", encoding="utf-8") as fh:
                fh.write(f"\n===== {message.uid} (dry_run={dry_run}) =====\n{transcript}\n")

        if result.returncode != 0:
            raise RuntimeError(
                f"Claude Code exited {result.returncode}: {result.stderr.strip()[:500]}"
            )
        log.info("Claude agent done (%s): %s", message.uid, transcript[:300])

        # Optionally act on a success marker in the agent's report (e.g. delete
        # the triggering email only if the request was actually approved).
        marker = self.spec.get("delete_message_on")
        if marker and not dry_run and re.search(marker, transcript):
            try:
                from ..graph import GraphClient

                gid = message.uid.split(":", 1)[1] if ":" in message.uid else ""
                if gid:
                    GraphClient().delete_message(gid)
                    log.info("Deleted message %s (matched %r)", message.uid, marker)
            except Exception as exc:
                log.warning("Delete-on-success failed for %s: %s", message.uid, exc)
