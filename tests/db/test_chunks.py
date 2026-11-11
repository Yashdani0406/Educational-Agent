import sqlite3
from datetime import UTC, datetime

import pytest

from eduagent.db.chunks import ChunksRepo, KeywordFilters, StoredChunk, chunk_id, fts_query
from eduagent.db.courses import CoursesRepo
from eduagent.db.database import Database
from eduagent.db.files import FilesRepo


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "study.db")
    d.migrate()
    return d


@pytest.fixture
def repo(db):
    return ChunksRepo(db, lambda: datetime(2026, 11, 11, 9, 0, tzinfo=UTC))


@pytest.fixture
def courses(db):
    return CoursesRepo(db)


@pytest.fixture
def course(courses):
    return courses.create_course("ML")


@pytest.fixture
def files(db):
    return FilesRepo(db)


def make_file(files, course_id, name="a.pdf", module_id=None, origin="module"):
    return files.add(course_id, module_id, origin, "pdf", name, name, None, f"hash-{name}")


def chunk(f, seq, text, heading="", kind="source", module_id=None, piece=0):
    return StoredChunk(
        id=chunk_id(f.id, piece, seq), file_id=f.id, course_id=f.course_id, module_id=module_id,
        origin=f.origin, kind=kind, seq=seq, text=text, heading_path=heading, loc_kind="page",
        loc_start=seq, loc_end=seq, word_count=len(text.split()),
    )


def ids(hits):
    return [h[0] for h in hits]


def test_chunk_id_format():
    assert chunk_id(12, 3, 7) == "f12-0003-007"


def test_underscore_term_is_one_token(repo, files, course):
    f = make_file(files, course.id)
    a = chunk(f, 0, "use train_test_split here")
    b = chunk(f, 1, "train the model; test it; split data")
    repo.upsert([a, b])
    hits = repo.keyword_search("train_test_split", course.id, "module")
    assert ids(hits) == [a.id]


def test_fts_query_sanitises(repo, files, course):
    q = fts_query('what is "Gini" (index)? AND OR*')
    assert q == '"what" OR "is" OR "Gini" OR "index" OR "AND" OR "OR"'
    f = make_file(files, course.id)
    repo.upsert([chunk(f, 0, "the gini index")])
    assert ids(repo.keyword_search('what is "Gini" (index)? AND OR*', course.id, "module")) == [chunk_id(f.id, 0, 0)]
    assert fts_query("?!") is None
    assert repo.keyword_search("?!", course.id, "module") == []
    # no syntax error even for hostile punctuation
    try:
        repo.keyword_search('NEAR( ) ^ - : "', course.id, "module")
    except sqlite3.OperationalError:  # pragma: no cover
        pytest.fail("fts syntax leaked")


def test_upsert_idempotent(repo, db, files, course):
    f = make_file(files, course.id)
    a = chunk(f, 0, "alpha beta")
    repo.upsert([a])
    repo.upsert([a])

    def count(table):
        with db.connect() as conn:
            return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    assert count("chunks_fts") == 1 and count("chunks") == 1
    repo.upsert([chunk(f, 0, "gamma delta")])
    assert count("chunks_fts") == 1
    assert repo.keyword_search("alpha", course.id, "module") == []
    assert ids(repo.keyword_search("gamma", course.id, "module")) == [a.id]
    assert repo.for_file(f.id)[0].text == "gamma delta"


def test_filters(repo, files, courses, course):
    m1, m2 = courses.add_module(course.id, "M1"), courses.add_module(course.id, "M2")
    t = courses.add_topic(course.id, "Trees")
    f1 = make_file(files, course.id, "a.pdf", module_id=m1)
    f2 = make_file(files, course.id, "b.pdf", module_id=m2)
    ref = make_file(files, course.id, "book.pdf", origin="reference")
    other_course = courses.create_course("Stats")
    fo = make_file(files, other_course.id, "o.pdf")
    c1 = chunk(f1, 0, "entropy of a tree", module_id=m1)
    c2 = chunk(f2, 0, "entropy of a split", module_id=m2, kind="web")
    c3 = chunk(ref, 0, "entropy in the book")
    c4 = chunk(fo, 0, "entropy elsewhere")
    repo.upsert([c1, c2, c3, c4])
    repo.link_topics([(c1.id, t)])

    def search(origin="module", **kw):
        return set(ids(repo.keyword_search("entropy", course.id, origin, KeywordFilters(**kw))))

    assert search() == {c1.id, c2.id}
    assert search(origin="reference") == {c3.id}
    assert search(module_id=m2) == {c2.id}
    assert search(topic_id=t) == {c1.id}
    assert search(file_id=f1.id) == {c1.id}
    assert search(kind="web") == {c2.id}
    assert c4.id not in search() | search(origin="reference")
    assert ids(repo.keyword_search("entropy", other_course.id, "module")) == [c4.id]


def test_delete_file_records_removed(repo, db, files, courses, course):
    t = courses.add_topic(course.id, "Trees")
    f = make_file(files, course.id, "Lecture 1.pdf")
    keep = make_file(files, course.id, "keep.pdf")
    a, b, k = chunk(f, 0, "entropy one"), chunk(f, 1, "entropy two"), chunk(keep, 0, "entropy keep")
    repo.upsert([a, b, k])
    repo.link_topics([(a.id, t), (k.id, t)])
    assert repo.delete_file(f.id, "Lecture 1.pdf", "deleted") == [a.id, b.id]
    assert repo.for_file(f.id) == []
    assert ids(repo.keyword_search("entropy", course.id, "module")) == [k.id]
    got = repo.removed([a.id, b.id, k.id])
    assert set(got) == {a.id, b.id}
    assert (got[a.id].reason, got[a.id].file_title, got[a.id].file_id) == ("deleted", "Lecture 1.pdf", f.id)
    assert got[a.id].removed_at == "2026-11-11T09:00:00+00:00"
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM chunk_topics").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM chunks_fts").fetchone()[0] == 1


def test_topic_chunks_order_and_module_filter(repo, files, courses, course):
    m1, m2 = courses.add_module(course.id, "M1"), courses.add_module(course.id, "M2")
    t = courses.add_topic(course.id, "Trees")
    f1 = make_file(files, course.id, "a.pdf", module_id=m1)
    f2 = make_file(files, course.id, "b.pdf", module_id=m2)
    c = [chunk(f2, 0, "b0", module_id=m2), chunk(f1, 1, "a1", module_id=m1), chunk(f1, 0, "a0", module_id=m1)]
    repo.upsert(c)
    repo.link_topics([(x.id, t) for x in c])
    assert [x.text for x in repo.topic_chunks(t)] == ["a0", "a1", "b0"]
    assert [x.text for x in repo.topic_chunks(t, module_id=m2)] == ["b0"]
    assert [x.text for x in repo.topic_chunks(t, course_id=course.id + 99)] == []
    assert repo.topics_supported_in_module(m1) == {t}
    repo.unlink_file_topics(f1.id)
    assert repo.topics_supported_in_module(m1) == set()
    assert repo.topics_supported_in_module(m2) == {t}
    repo.set_module(f2.id, m1)
    assert repo.topics_supported_in_module(m1) == {t}
    assert repo.get_many([c[2].id, "nope", c[0].id])[0].text == "a0"
    assert [x.module_id for x in repo.get_many([c[0].id])] == [m1]
