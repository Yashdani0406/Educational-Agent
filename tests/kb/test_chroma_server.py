import json
import socket
import subprocess
import sys
from pathlib import Path

from eduagent.kb.chroma_server import ChromaServer


def test_server_starts_and_stops(new_settings):
    tmp_path = new_settings.data_dir
    server = ChromaServer(new_settings)
    assert server.start() is None
    assert server.healthy()
    proc = server._process
    server.stop()
    assert not server.healthy()
    assert not (tmp_path / "chroma_server.json").exists()
    assert proc.poll() is not None
    assert (tmp_path / "logs" / "chroma.log").exists()


def test_adopts_own_leftover_server(new_settings):
    first, second = ChromaServer(new_settings), ChromaServer(new_settings)
    assert first.start() is None
    leftover, first._process = first._process, None  # the app died without stopping it
    try:
        assert second.start() is None
        assert second.healthy()
        second.stop()
        assert not second.healthy()
        assert not (new_settings.data_dir / "chroma_server.json").exists()
    finally:
        leftover.terminate()
        leftover.wait()


def test_foreign_server_is_refused_and_left_alone(new_settings):
    owner, other = ChromaServer(new_settings), ChromaServer(new_settings)
    assert owner.start() is None
    (new_settings.data_dir / "chroma_server.json").unlink()  # now nothing says it is ours
    try:
        warning = other.start()
        assert warning.startswith("Chroma (the search database) didn't start")
        assert f"port {new_settings.chroma_port} is already used by another program" in warning
        other.stop()
        assert owner.healthy()
    finally:
        owner.stop()


def test_stale_marker_does_not_block_launch(new_settings):
    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()
    marker = new_settings.data_dir / "chroma_server.json"
    marker.write_text(
        json.dumps({"pid": done.pid, "port": new_settings.chroma_port, "path": str(new_settings.chroma_dir.resolve())})
    )
    server = ChromaServer(new_settings)
    try:
        assert server.start() is None
        assert json.loads(marker.read_text())["pid"] == server._process.pid
    finally:
        server.stop()


def test_port_taken_by_non_chroma_returns_warning(new_settings):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", new_settings.chroma_port))
        busy.listen()
        server = ChromaServer(new_settings)
        warning = server.start()
        assert warning.startswith("Chroma (the search database) didn't start")
        assert str(new_settings.chroma_port) in warning
        assert server._process is None
        assert not (new_settings.data_dir / "chroma_server.json").exists()


def test_bad_executable_returns_warning(new_settings):
    server = ChromaServer(new_settings, chroma_exe=Path("missing.exe"))
    warning = server.start()
    assert warning.startswith("Chroma (the search database) didn't start")
    assert "data/logs/chroma.log" in warning


def test_binds_localhost_only(new_settings):
    settings = new_settings.model_copy(update={"chroma_port": 8123})
    command = ChromaServer(settings, chroma_exe=Path("chroma")).command()
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--port") + 1] == "8123"
