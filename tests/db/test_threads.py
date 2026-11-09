import pytest

from eduagent.db.database import Database
from eduagent.db.threads import ThreadsRepo


def make(tmp_path):
    db = Database(tmp_path / "study.db")
    db.migrate()
    return ThreadsRepo(db)


def test_create_list_order(tmp_path):
    repo = make(tmp_path)
    a = repo.create(None)
    b = repo.create(None, "Second")
    assert a.title == "New chat" and b.title == "Second"
    assert [t.id for t in repo.list(None)] == [b.id, a.id]
    assert repo.list(None)[-1].id == a.id
    repo.rename(a.id, "Renamed")
    assert repo.get(a.id).title == "Renamed"
    with pytest.raises(KeyError):
        repo.get("nope")


def test_touch_updates_last_agent_and_order(tmp_path):
    repo = make(tmp_path)
    a = repo.create(None)
    b = repo.create(None)
    assert repo.list(None)[0].id == b.id
    repo.touch(a.id, "tutor")
    first = repo.list(None)[0]
    assert first.id == a.id and first.last_agent == "tutor"
