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
    assert proc.poll() is not None
    assert (tmp_path / "logs" / "chroma.log").exists()


def test_reuses_running_server(new_settings):
    first, second = ChromaServer(new_settings), ChromaServer(new_settings)
    try:
        assert first.start() is None
        assert second.start() is None
        second.stop()
        assert first.healthy()
    finally:
        first.stop()


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
