import threading
import time

import pytest

from eduagent.config import Settings
from eduagent.db.chunks import ChunksRepo, StoredChunk
from eduagent.db.courses import CoursesRepo
from eduagent.db.database import Database
from eduagent.db.files import FilesRepo
from eduagent.kb import rerank
from eduagent.kb.rerank import Reranker
from eduagent.kb.search import SHORTLIST, HybridSearcher, SearchFilters, allot_slots, tm2c2
from eduagent.kb.store import DenseHit


def test_tm2c2_values():
    fused = tm2c2({"a": 1.0, "b": 0.0}, {"b": 8.0, "c": 4.0}, 0.6)
    assert fused == pytest.approx({"a": 0.6, "b": 0.7, "c": 0.2})


def test_tm2c2_empty_lists():
    assert tm2c2({}, {}, 0.6) == {}
    assert tm2c2({}, {"x": 3.0}, 0.6) == pytest.approx({"x": 0.4})


@pytest.mark.parametrize(
    "args, expected",
    [
        ((10, 0.7, 7, 3, 30, 30), (7, 3)),
        ((10, 0.7, 7, 0, 30, 0), (10, 0)),  # no books
        ((10, 0.7, 0, 9, 30, 30), (0, 10)),  # a question only the book covers
        ((10, 0.7, 4, 3, 4, 30), (4, 6)),  # only 4 module chunks exist
        ((10, 0.7, 1, 0, 30, 30), (7, 3)),  # one relevant module chunk and nothing relevant in books: no slot to the books' junk
        ((10, 0.7, 0, 0, 5, 3), (5, 3)),  # nothing relevant: the floor never empties results
    ],
)
def test_allot_slots(args, expected):
    assert allot_slots(*args) == expected


class FakeEmbedder:
    def embed_query(self, text):
        return [1.0, 0.0]


class FakeStore:
    def __init__(self, hits=None):
        self.hits = hits or {}  # origin -> [DenseHit]
        self.calls = []

    def query(self, vector, course_id, origin, **kwargs):
        self.calls.append((course_id, origin, kwargs))
        return self.hits.get(origin, [])


class FakeReranker:
    def __init__(self, scores):
        self.scores = scores  # chunk text -> score

    def score(self, query, texts):
        return [next(v for k, v in self.scores.items() if k in t) for t in texts]


def stored(cid, text, origin="module", course_id=1, module_id=1, file_id=1, kind="source"):
    return StoredChunk(cid, file_id, course_id, module_id, origin, kind, 0, text, "", "slide", 1, 1, len(text.split()))


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "study.db")
    d.migrate()
    return d


@pytest.fixture
def repo(db):
    course = CoursesRepo(db).create_course("ML")
    assert course.id == 1
    return ChunksRepo(db)


def make(repo, store, reranker=None, **settings):
    s = Settings(_env_file=None, **settings)
    return HybridSearcher(s, repo, store, FakeEmbedder(), reranker)


def seed(db):
    """Three files in course 1 (ids 1-3: slides, book, second deck) and modules 1 and 2, through the real repos."""
    courses, files = CoursesRepo(db), FilesRepo(db)
    assert courses.add_module(1, "Trees") == 1 and courses.add_module(1, "Other") == 2
    files.add(1, 1, "module", "pptx", "Trees", "trees.pptx", None, "h1")
    files.add(1, None, "reference", "pdf", "Book", "book.pdf", None, "h2")
    files.add(1, 1, "module", "pptx", "More trees", "more.pptx", None, "h3")


def test_keyword_only_hit_reaches_results(repo, db):
    seed(db)
    repo.upsert([stored("k", "call train_test_split before you fit"), stored("d", "unrelated words about trees")])
    store = FakeStore({"module": [DenseHit("d", 0.5)]})
    result = make(repo, store).search("train_test_split", 1)
    ids = [h.chunk.id for h in result.hits]
    assert "k" in ids and "d" in ids
    hit = next(h for h in result.hits if h.chunk.id == "k")
    assert hit.dense == 0.0 and hit.keyword > 0


def test_reranker_disabled_orders_by_fused(repo, db):
    seed(db)
    repo.upsert([stored("a", "alpha"), stored("b", "beta"), stored("c", "gamma")])
    store = FakeStore({"module": [DenseHit("a", 0.2), DenseHit("b", 0.9), DenseHit("c", 0.5)]})
    off = make(repo, store, FakeReranker({"alpha": 9, "beta": 0, "gamma": 5}), rerank_enabled=False).search("q", 1)
    assert [h.chunk.id for h in off.hits] == ["b", "c", "a"]
    assert all(h.rerank is None for h in off.hits) and off.trace["reranker"] is False
    assert [h.chunk.id for h in make(repo, store, None).search("q", 1).hits] == ["b", "c", "a"]


def test_reranker_reorders(repo, db):
    seed(db)
    repo.upsert([stored("a", "alpha"), stored("b", "beta"), stored("c", "gamma")])
    store = FakeStore({"module": [DenseHit("a", 0.2), DenseHit("b", 0.9), DenseHit("c", 0.5)]})
    result = make(repo, store, FakeReranker({"alpha": 9, "beta": 0, "gamma": 5})).search("q", 1)
    assert [h.chunk.id for h in result.hits] == ["a", "c", "b"]
    assert result.hits[0].rerank == 9 and result.trace["k"]["rerank_in"] == 3


def test_floor_moves_slots_to_books(repo, db):
    seed(db)
    repo.upsert(
        [stored(f"m{i}", f"modtext{i}") for i in range(8)]
        + [stored(f"r{i}", f"booktext{i}", origin="reference", module_id=None, file_id=2) for i in range(9)]
    )
    store = FakeStore({
        "module": [DenseHit(f"m{i}", 0.5) for i in range(8)],
        "reference": [DenseHit(f"r{i}", 0.5) for i in range(9)],
    })
    scores = {f"modtext{i}": -8.0 for i in range(8)} | {f"booktext{i}": 5.0 for i in range(9)}
    result = make(repo, store, FakeReranker(scores)).search("q", 1)
    assert result.trace["slots"] == {"module": 1, "reference": 9}
    assert sum(h.origin == "reference" for h in result.hits) == 9
    # the spare slot went to the module group, but its chunk is below the floor, so it is cut
    assert len(result.hits) == 9 and result.trace["cut"] == 1
    assert all(h.rerank >= -2.8 and not h.weak for h in result.hits)


def test_below_floor_hits_are_dropped(repo, db):
    seed(db)
    repo.upsert([stored("a", "alpha"), stored("b", "beta"), stored("c", "gamma")])
    store = FakeStore({"module": [DenseHit("a", 0.5), DenseHit("b", 0.5), DenseHit("c", 0.5)]})
    result = make(repo, store, FakeReranker({"alpha": 4.0, "beta": -2.8, "gamma": -2.81})).search("q", 1)
    assert [h.chunk.id for h in result.hits] == ["a", "b"]  # the floor itself passes
    assert result.trace["cut"] == 1 and result.trace["k"]["returned"] == 2
    assert [c["weak"] for c in result.trace["chunks"]] == [False, False]


def test_all_below_floor_returns_three_weak_best_first(repo, db):
    seed(db)
    repo.upsert([stored(f"m{i}", f"mod{i}") for i in range(4)] + [stored("r0", "book0", origin="reference", module_id=None, file_id=2)])
    store = FakeStore({"module": [DenseHit(f"m{i}", 0.5) for i in range(4)], "reference": [DenseHit("r0", 0.5)]})
    scores = {"mod0": -5.0, "mod1": -9.0, "mod2": -6.0, "mod3": -7.0, "book0": -4.0}
    result = make(repo, store, FakeReranker(scores)).search("q", 1)
    assert [h.chunk.id for h in result.hits] == ["r0", "m0", "m2"]
    assert all(h.weak for h in result.hits)
    assert [c["weak"] for c in result.trace["chunks"]] == [True] * 3 and result.trace["k"]["returned"] == 3


def test_reranker_off_cuts_nothing(repo, db):
    seed(db)
    repo.upsert([stored("a", "alpha"), stored("b", "beta")])
    store = FakeStore({"module": [DenseHit("a", 0.5), DenseHit("b", 0.4)]})
    for searcher in (make(repo, store, FakeReranker({"alpha": -50, "beta": -50}), rerank_enabled=False), make(repo, store, None)):
        result = searcher.search("q", 1)
        assert len(result.hits) == 2 and not any(h.weak for h in result.hits) and result.trace["cut"] == 0


def test_filters_passed_to_both_searches(repo, db):
    seed(db)
    repo.upsert([stored("a", "alpha topicword")])
    topic = CoursesRepo(db).add_topic(1, "Trees")
    repo.link_topics([("a", topic)])
    store = FakeStore({"module": [DenseHit("a", 0.5)]})
    filters = SearchFilters(module_id=1, topic_id=topic, file_id=1, kind="source")
    result = make(repo, store).search("topicword", 1, filters)
    for _, _, kwargs in store.calls:
        assert kwargs["module_id"] == 1 and kwargs["file_id"] == 1 and kwargs["kind"] == "source"
        assert kwargs["chunk_ids"] == ["a"] and kwargs["k"] == SHORTLIST
    assert [h.chunk.id for h in result.hits] == ["a"]  # the keyword side accepted all four filters too
    # Reachable only by keyword (the dense fake never returns them): another module and another file.
    repo.upsert([stored("other-module", "alpha topicword", module_id=2), stored("other-file", "alpha topicword", file_id=3)])
    quiet = FakeStore()  # only the keyword side can answer here
    assert [h.chunk.id for h in make(repo, quiet).search("topicword", 1, SearchFilters(module_id=1, file_id=1)).hits] == ["a"]
    assert {h.chunk.id for h in make(repo, quiet).search("topicword", 1, SearchFilters(module_id=2)).hits} == {"other-module"}
    assert {h.chunk.id for h in make(repo, quiet).search("topicword", 1, SearchFilters(file_id=3)).hits} == {"other-file"}
    assert make(repo, quiet).search("topicword", 1, SearchFilters(kind="web")).hits == []
    assert make(repo, quiet).search("topicword", 1, SearchFilters(topic_id=topic + 99)).hits == []
    assert quiet.calls[-1][2]["chunk_ids"] == []


def test_trace_has_all_fields(repo, db):
    seed(db)
    repo.upsert([stored("a", "alpha"), stored("r", "beta", origin="reference", module_id=None, file_id=2)])
    store = FakeStore({"module": [DenseHit("a", 0.5)], "reference": [DenseHit("r", 0.25)]})
    for query, searcher in [("alpha", make(repo, store, FakeReranker({"alpha": 1.23456, "beta": -2}))), ("zzz", make(repo, FakeStore()))]:
        trace = searcher.search(query, 1).trace
        assert set(trace) == {"query", "filters", "alpha", "reranker", "k", "slots", "cut", "ms", "chunks"}
        assert set(trace["k"]) == {"dense", "keyword", "rerank_in", "returned"}
        assert set(trace["slots"]) == {"module", "reference"}
        assert set(trace["ms"]) == {"embed", "dense", "keyword", "fusion", "rerank", "total"}
        assert all(v >= 0 for v in trace["ms"].values()) and trace["k"]["dense"] == 30
        assert trace["k"]["returned"] == len(trace["chunks"])
        assert set(trace["filters"]) == {"module_id", "topic_id", "file_id", "kind"}
    first = make(repo, store, FakeReranker({"alpha": 1.23456, "beta": -2})).search("alpha", 1).trace["chunks"][0]
    assert set(first) == {"id", "origin", "dense", "keyword", "fused", "rerank", "weak"} and first["rerank"] == 1.235 and first["weak"] is False


def test_course_scoped(repo, db):
    seed(db)
    other = CoursesRepo(db).create_course("Other").id
    theirs = FilesRepo(db).add(other, None, "module", "pdf", "t", "t.pdf", None, "h9")
    repo.upsert([stored("mine", "shared words"), stored("theirs", "shared words", course_id=other, module_id=None, file_id=theirs.id)])
    store = FakeStore({"module": [DenseHit("mine", 0.5), DenseHit("theirs", 0.9)]})  # a leaky store
    result = make(repo, store).search("shared words", 1)
    assert store.calls[0][0] == 1
    assert [h.chunk.id for h in result.hits] == ["mine"]
    kw_only = make(repo, FakeStore()).search("shared words", 1)
    assert [h.chunk.id for h in kw_only.hits] == ["mine"]


def test_stale_vector_without_sqlite_row_is_skipped(repo, db):
    seed(db)
    repo.upsert([stored("a", "alpha")])
    store = FakeStore({"module": [DenseHit("ghost", 0.9), DenseHit("a", 0.5)]})
    assert [h.chunk.id for h in make(repo, store).search("q", 1).hits] == ["a"]


def test_total_defaults_to_setting_and_can_be_overridden(repo, db):
    seed(db)
    repo.upsert([stored(f"m{i}", f"w{i}") for i in range(6)])
    store = FakeStore({"module": [DenseHit(f"m{i}", 0.5) for i in range(6)]})
    assert len(make(repo, store, search_results=4).search("q", 1).hits) == 4
    assert len(make(repo, store, search_results=4).search("q", 1, total=2).hits) == 2


def test_reranker_loads_model_once_across_threads(tmp_path, monkeypatch):
    loads = []

    class SlowEncoder:
        def __init__(self, *args, **kwargs):
            loads.append(1)
            time.sleep(0.2)

        def rerank(self, query, documents):
            return iter([1.0 for _ in documents])

    monkeypatch.setattr(rerank, "_encoder_class", lambda: SlowEncoder)
    r = Reranker(Settings(_env_file=None, models_dir=tmp_path))
    threads = [threading.Thread(target=r.score, args=("q", ["a"])) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(loads) == 1
