import pytest

from eduagent.db.chunks import StoredChunk
from eduagent.kb.store import VectorStore


def chunk(cid, file_id=1, course_id=1, module_id=None, origin="module"):
    return StoredChunk(cid, file_id, course_id, module_id, origin, "source", 0, "t", "", "page", 1, 1, 1)


@pytest.fixture
def store(chroma_port):
    s = VectorStore(chroma_port)
    s._client.delete_collection(VectorStore.COLLECTION)
    return VectorStore(chroma_port)


def test_upsert_query_scoped(store):
    store.upsert([chunk("a", course_id=1), chunk("b", course_id=1), chunk("c", course_id=2), chunk("d", course_id=1, origin="reference")],
                 [[1, 0, 0], [0.8, 0.6, 0], [1, 0, 0], [1, 0, 0]], uploaded_week=1)
    hits = store.query([1, 0, 0], course_id=1, origin="module")
    assert [h.chunk_id for h in hits] == ["a", "b"]
    assert hits[0].similarity == pytest.approx(1.0, abs=1e-4)
    assert hits[1].similarity == pytest.approx(0.8, abs=1e-4)
    assert all(-1 <= h.similarity <= 1 for h in hits)


def test_upsert_same_ids_no_duplicates(store):
    for _ in range(2):
        store.upsert([chunk("a"), chunk("b")], [[1, 0], [0, 1]], uploaded_week=1)
    assert store.count() == 2


def test_delete_file(store):
    store.upsert([chunk("a", file_id=1), chunk("b", file_id=2)], [[1, 0], [0, 1]], uploaded_week=1)
    store.delete_file(1)
    assert store.count() == 1 and store.count(file_id=1) == 0
    assert [h.chunk_id for h in store.query([1, 0], 1, "module")] == ["b"]


def test_set_module_relabels(store):
    store.upsert([chunk("a", module_id=1), chunk("b", module_id=1)], [[1, 0], [0, 1]], uploaded_week=1)
    store.set_module(1, 2)
    assert store.query([1, 0], 1, "module", module_id=1) == []
    assert {h.chunk_id for h in store.query([1, 0], 1, "module", module_id=2)} == {"a", "b"}


def test_chunk_ids_filter(store):
    store.upsert([chunk("a"), chunk("b"), chunk("c")], [[1, 0], [0.9, 0.1], [0, 1]], uploaded_week=1)
    assert {h.chunk_id for h in store.query([1, 0], 1, "module", chunk_ids=["b", "c"])} == {"b", "c"}
    assert store.query([1, 0], 1, "module", chunk_ids=[]) == []
