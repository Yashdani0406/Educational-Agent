"""Starts and stops the local Chroma server (`chroma run`) that holds the search vectors."""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

from eduagent.config import Settings

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Starts the local Chroma search database when the app starts and stops it when the app closes."

HOST = "127.0.0.1"


class ChromaServer:
    def __init__(self, settings: Settings, *, chroma_exe: Path | None = None, health_timeout_s: float = 30):
        self._settings = settings
        self._exe = chroma_exe or Path(sys.executable).parent / ("chroma.exe" if os.name == "nt" else "chroma")
        self._timeout = health_timeout_s
        self._process: subprocess.Popen | None = None

    def command(self) -> list[str]:
        s = self._settings
        return [str(self._exe), "run", "--path", str(s.chroma_dir), "--host", HOST, "--port", str(s.chroma_port)]

    def healthy(self) -> bool:
        try:
            return httpx.get(f"http://{HOST}:{self._settings.chroma_port}/api/v2/heartbeat", timeout=1).is_success
        except httpx.HTTPError:
            return False

    def start(self) -> str | None:
        """None when Chroma is ready, otherwise a warning to show the student. Never raises."""
        if self.healthy():
            log.info("Chroma already running on port %s; reusing it", self._settings.chroma_port)
            return None
        try:
            return self._launch()
        except OSError as e:
            log.exception("Could not start Chroma")
            return self._warning(str(e))

    def _launch(self) -> str | None:
        log_dir = self._settings.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        self._settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with open(log_dir / "chroma.log", "ab") as out:
            self._process = subprocess.Popen(
                self.command(),
                stdout=out,
                stderr=out,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
                env={**os.environ, "ANONYMIZED_TELEMETRY": "False", "CHROMA_ANONYMIZED_TELEMETRY": "False"},
            )
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                code = self._process.returncode
                self._process = None
                return self._warning(f"it stopped straight away (exit code {code})")
            if self.healthy():
                log.info("Chroma started on port %s", self._settings.chroma_port)
                return None
            time.sleep(0.2)
        self.stop()
        return self._warning(f"it didn't answer within {self._timeout:g} seconds")

    @staticmethod
    def _warning(reason: str) -> str:
        return (
            f"Chroma (the search database) didn't start: {reason}. "
            "Uploads and search are paused until it does; details in data/logs/chroma.log."
        )

    def stop(self) -> None:
        """Stop the server we started; leave one we merely reused alone."""
        process, self._process = self._process, None
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.info("Chroma stopped")
