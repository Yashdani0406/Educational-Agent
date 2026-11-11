"""Starts and stops the local Chroma server (`chroma run`) that holds the search vectors."""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from eduagent.config import Settings

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Starts the local Chroma search database when the app starts and stops it when the app closes."

HOST = "127.0.0.1"
_STILL_ACTIVE = 259


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == _STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # signal 0 only checks; on Windows os.kill would kill, hence the branch above
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class ChromaServer:
    def __init__(self, settings: Settings, *, chroma_exe: Path | None = None, health_timeout_s: float = 30):
        self._settings = settings
        self._exe = chroma_exe or Path(sys.executable).parent / ("chroma.exe" if os.name == "nt" else "chroma")
        self._timeout = health_timeout_s
        self._process: subprocess.Popen | None = None
        self._adopted_pid: int | None = None  # a leftover server of ours that we took over

    @property
    def _marker(self) -> Path:
        # Beside the Chroma folder, not in it: Chroma owns that folder.
        return self._settings.data_dir / "chroma_server.json"

    def _marker_pid(self) -> int | None:
        """The pid in our marker if it describes a live server for this port and folder, else None."""
        try:
            data = json.loads(self._marker.read_text(encoding="utf-8"))
            same = data["port"] == self._settings.chroma_port and data["path"] == str(self._settings.chroma_dir.resolve())
            pid = int(data["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return pid if same and _pid_alive(pid) else None

    def _write_marker(self, pid: int) -> None:
        data = {"pid": pid, "port": self._settings.chroma_port, "path": str(self._settings.chroma_dir.resolve())}
        self._marker.write_text(json.dumps(data), encoding="utf-8")

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
        port = self._settings.chroma_port
        if self.healthy():
            pid = self._marker_pid()
            if pid is None:
                log.warning("Something that is not our Chroma already answers on port %s; not using it", port)
                return self._warning(f"port {port} is already used by another program")
            self._adopted_pid = pid
            log.info("Adopted our leftover Chroma server (pid %s) on port %s", pid, port)
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
        self._write_marker(self._process.pid)
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                code = self._process.returncode
                self._process = None
                if self.healthy() and self._marker_pid() is not None:  # it lost a race to our own server
                    return None
                self._marker.unlink(missing_ok=True)
                return self._warning(f"it stopped straight away (exit code {code}), is port {self._settings.chroma_port} in use?")
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
        """Stop a server that is ours (started now or adopted); never touch anyone else's."""
        process, self._process = self._process, None
        pid, self._adopted_pid = self._adopted_pid, None
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        elif pid is not None:
            try:
                os.kill(pid, signal.SIGTERM)  # on Windows this is TerminateProcess
            except OSError:
                pass
            deadline = time.monotonic() + 10
            while _pid_alive(pid) and time.monotonic() < deadline:
                time.sleep(0.1)
        else:
            return
        self._marker.unlink(missing_ok=True)
        log.info("Chroma stopped")
