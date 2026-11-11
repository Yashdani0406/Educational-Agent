import socket

import pytest

from eduagent.config import Settings
from eduagent.kb.chroma_server import ChromaServer


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_settings(tmp_path, port: int) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, chroma_port=port)


@pytest.fixture
def new_settings(tmp_path):
    """Settings for a throwaway data dir and a free port."""
    return make_settings(tmp_path, free_port())


@pytest.fixture(scope="session")
def chroma_port(tmp_path_factory):
    port = free_port()
    server = ChromaServer(make_settings(tmp_path_factory.mktemp("chroma"), port))
    warning = server.start()
    assert warning is None, warning
    yield port
    server.stop()
