"""Run a local script or command when a message matches.

Config keys:

* ``command`` (required) – the command line. Placeholders like ``{subject}``
  are substituted from the message.
* ``shell`` (default false) – run via the shell. Leave false and pass a list
  for safety; use a string only when you need shell features.
* ``cwd``     – working directory.
* ``env``     – extra environment variables (dict).
* ``timeout`` – seconds before the command is killed (default 300).
* ``pass_body_stdin`` (default false) – feed the message body to stdin.

Selected message fields are also exported as ``ALFRED_*`` environment
variables (``ALFRED_SUBJECT``, ``ALFRED_FROM``, ``ALFRED_UID``) so scripts can
read them without templating.
"""

from __future__ import annotations

import logging
import os
import subprocess

from ..models import Message
from .base import Workflow

log = logging.getLogger("alfred.run_command")


class RunCommand(Workflow):
    def run(self, message: Message) -> None:
        command = self.spec.get("command")
        if not command:
            raise ValueError("run_command requires a 'command'")

        shell = bool(self.spec.get("shell", False))
        if isinstance(command, list):
            command = [self.render(str(part), message) for part in command]
        else:
            command = self.render(str(command), message)

        env = dict(os.environ)
        env.update({str(k): str(v) for k, v in self.spec.get("env", {}).items()})
        env["ALFRED_SUBJECT"] = message.subject
        env["ALFRED_FROM"] = message.from_addr
        env["ALFRED_UID"] = message.uid

        stdin = message.body_text if self.spec.get("pass_body_stdin") else None

        result = subprocess.run(
            command,
            shell=shell,
            cwd=self.spec.get("cwd"),
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=int(self.spec.get("timeout", 300)),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Command exited {result.returncode}: {result.stderr.strip()[:1000]}"
            )
        out = result.stdout.strip()
        log.info("Command ok (%s):\n%s", message.uid, out if out else "(no output)")
