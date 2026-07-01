"""The main loop: poll the source, dispatch new messages, persist state."""

from __future__ import annotations

import logging
import signal
import time

from .config import Config
from .dispatcher import Dispatcher
from .sources import build_source
from .state import State

log = logging.getLogger("alfred.engine")


class Engine:
    def __init__(self, config: Config):
        self.config = config
        self.source = build_source(config.source)
        self.dispatcher = Dispatcher(config.rules)
        self.state = State(config.state_file)
        self._running = False

    def _process_once(self) -> int:
        handled = 0
        for message in self.source.fetch_new():
            if self.state.is_processed(self.source.name, message.uid):
                continue
            try:
                self.dispatcher.dispatch(message)
            finally:
                # Mark processed even if a workflow raised, so a persistently
                # failing message can't wedge the loop. Failures are logged.
                self.state.mark_processed(self.source.name, message.uid)
                handled += 1
        if handled:
            self.state.save()
        return handled

    def run_forever(self) -> None:
        self._running = True

        def _stop(signum, frame):
            log.info("Received signal %s, shutting down after this cycle.", signum)
            self._running = False

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        log.info(
            "Alfred started. Source=%s, rules=%d, poll=%ds",
            self.source.name,
            len(self.config.rules),
            self.config.poll_seconds,
        )
        while self._running:
            try:
                n = self._process_once()
                if n:
                    log.info("Processed %d new message(s).", n)
            except Exception as exc:  # a bad poll should not kill the daemon
                log.exception("Poll cycle failed: %s", exc)
            # Sleep in short slices so signals are handled promptly.
            for _ in range(self.config.poll_seconds):
                if not self._running:
                    break
                time.sleep(1)

        self.source.close()
        log.info("Alfred stopped.")

    def run_once(self) -> int:
        """Single pass — handy for testing a config without looping."""
        n = self._process_once()
        self.source.close()
        return n
