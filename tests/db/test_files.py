import sqlite3
from datetime import UTC, datetime

import pytest

from eduagent.db.courses import CoursesRepo
from eduagent.db.database import Database
from eduagent.db.files import FilesRepo


class Clock:
    def __init__(self, when: datetime) -> None:
        self.when = when

    def __call__(self) -> datetime:
        return self.when


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "study.db")
    d.migrate()
    return d


@pytest.fixture
def clock():
    return Clock(datetime(2026, 11, 4, 12, 0, tzinfo=UTC))


@pytest.fixture
def repo(db, clock):
    return FilesRepo(db, clock)


@pytest.fixture
def course(db):
    return CoursesRepo(db).create_course("ML")


def add(repo, course_id, name="a.pdf", h=None, module_id=None, origin="module", kind="pdf"):
    return repo.add(course_id, module_id, origin, kind, name, name, f"sources/{name}", h or f"hash-{name}")


def test_queue_fifo_and_positions(repo, course):
    a, b, c = (add(repo, course.id, n) for n in ("a.pdf", "b.pdf", "c.pdf"))
    assert repo.next_active().id == a.id
    assert [repo.queue_position(f.id) for f in (a, b, c)] == [1, 2, 3]
    repo.set_status(a.id, "done")
    assert repo.next_active().id == b.id
    assert repo.queue_position(b.id) == 1
    assert repo.queue_position(a.id) is None


def test_next_active_exclude(repo, course):
    a, b = add(repo, course.id, "a.pdf"), add(repo, course.id, "b.pdf")
    assert repo.next_active(exclude={a.id}).id == b.id
    assert repo.next_active(exclude={a.id, b.id}) is None


def test_duplicate_hash_rejected_per_course(repo, db, course):
    add(repo, course.id, "a.pdf", h="same")
    with pytest.raises(sqlite3.IntegrityError):
        add(repo, course.id, "b.pdf", h="same")
    other = CoursesRepo(db).create_course("Stats")
    add(repo, other.id, "a.pdf", h="same")


def test_week_label(repo, clock, db, course):
    first = add(repo, course.id, "a.pdf")
    assert first.uploaded_week == 1
    with db.connect() as conn:
        assert conn.execute("SELECT week1_monday FROM courses").fetchone()[0] == "2026-11-02"
    clock.when = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
    assert add(repo, course.id, "b.pdf").uploaded_week == 3
    repo.delete(first.id)
    assert add(repo, course.id, "c.pdf").uploaded_week == 3


def test_resume_finds_interrupted_file(db, repo, course):
    f = add(repo, course.id)
    repo.set_status(f.id, "embedding")
    assert FilesRepo(db).next_active().id == f.id


def test_pieces_idempotent_and_carry(repo, course):
    f = add(repo, course.id)
    repo.plan_pieces(f.id, [(1, 25), (26, 40)])
    repo.plan_pieces(f.id, [(1, 25), (26, 40)])
    assert len(repo.pieces(f.id)) == 2
    assert repo.get(f.id).pieces_total == 2
    assert repo.carry_headings(f.id, 0) == []
    repo.finish_piece(f.id, 0, ["Ch 1", "1.2 Trees"])
    assert repo.carry_headings(f.id, 1) == ["Ch 1", "1.2 Trees"]
    assert repo.get(f.id).pieces_done == 1
    assert [p.done for p in repo.pieces(f.id)] == [True, False]


def test_requeue_goes_to_end(repo, course):
    a, b = add(repo, course.id, "a.pdf"), add(repo, course.id, "b.pdf")
    repo.plan_pieces(a.id, [(1, 25)])
    repo.set_status(a.id, "failed", "boom")
    assert repo.get(a.id).error == "boom"
    repo.requeue(a.id)
    got = repo.get(a.id)
    assert (got.status, got.error, got.queue_pos) == ("queued", None, 3)
    assert repo.next_active().id == b.id
    assert len(repo.pieces(a.id)) == 1


def test_find_same_source_case_insensitive(repo, db, course):
    m = CoursesRepo(db).add_module(course.id, "M1")
    f = add(repo, course.id, "Lecture 1.PDF", module_id=m)
    assert repo.find_same_source(course.id, m, "module", "lecture 1.pdf").id == f.id
    assert repo.find_same_source(course.id, None, "module", "lecture 1.pdf") is None
    book = add(repo, course.id, "Book.pdf", origin="reference")
    assert repo.find_same_source(course.id, None, "reference", "book.PDF").id == book.id


def test_find_by_hash(repo, course):
    f = add(repo, course.id, "a.pdf", h="abc")
    assert repo.find_by_hash(course.id, "abc").id == f.id
    assert repo.find_by_hash(course.id, "nope") is None


def test_delete_cascades_pieces(repo, db, course):
    f = add(repo, course.id)
    repo.plan_pieces(f.id, [(1, 25)])
    repo.delete(f.id)
    with pytest.raises(KeyError):
        repo.get(f.id)
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM file_pieces").fetchone()[0] == 0


def test_setters_and_list(repo, db, course):
    m = CoursesRepo(db).add_module(course.id, "M1")
    f = repo.add(course.id, None, "reference", "web", "link", "http://x", None, None)
    repo.set_source(f.id, kind="web", title="Page", stored_path="sources/p.md", content_hash="h1")
    repo.set_layout(f.id, "web", None)
    repo.set_module(f.id, m)
    repo.set_topics_state(f.id, "pending")
    repo.set_trace(f.id, "t1")
    got = repo.get(f.id)
    assert (got.title, got.stored_path, got.content_hash, got.layout) == ("Page", "sources/p.md", "h1", "web")
    assert (got.module_id, got.topics_state, got.trace_id) == (m, "pending", "t1")
    assert [x.id for x in repo.list_course(course.id)] == [f.id]
    with pytest.raises(KeyError):
        repo.get(999)
