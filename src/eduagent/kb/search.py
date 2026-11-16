"""Finds the study chunks that answer a question: keyword and meaning search, fused, double-checked, split between lecture material and books."""

import logging
import time
from dataclasses import asdict, dataclass, replace

from eduagent.config import Settings
from eduagent.db.chunks import ChunkKind, ChunksRepo, KeywordFilters, StoredChunk
from eduagent.db.files import Origin
from eduagent.kb.embed import Embedder
from eduagent.kb.rerank import Reranker
from eduagent.kb.store import VectorStore

log = logging.getLogger(__name__)

WHAT_IT_DOES = (
    "Looks up the best study passages for a question by keyword and by meaning, double-checks them, "
    "and keeps a fair share for both lecture material and books."
)

SHORTLIST = 30
WEAK_FALLBACK = 3  # hits returned (marked weak) when nothing reaches RERANK_RELEVANT_MIN
# A passage counts as relevant when the reranker scores it at least this high. It only decides which group gives
# slots to the other; it moves slots and cuts results below it (the 3 best come back marked weak if none pass). Calibrated in tests/kb/search_calibration.md.
RERANK_RELEVANT_MIN = -2.8  # every labelled answer scored >= -2.20; non-answers below that scored <= -3.39 (see search_calibration.md)
ORIGINS: tuple[Origin, Origin] = ("module", "reference")


@dataclass(frozen=True)
class SearchFilters:
    module_id: int | None = None
    topic_id: int | None = None
    file_id: int | None = None
    kind: ChunkKind | None = None


@dataclass(frozen=True)
class Hit:
    chunk: StoredChunk
    origin: Origin
    dense: float
    keyword: float
    fused: float
    rerank: float | None
    weak: bool = False  # below the relevance floor, returned only because nothing else passed


@dataclass(frozen=True)
class SearchResult:
    hits: list[Hit]
    trace: dict


def tm2c2(dense: dict[str, float], keyword: dict[str, float], alpha: float) -> dict[str, float]:
    """Convex combination after theoretical min-max normalisation: cosine similarity from -1, keyword score from 0."""
    max_sim = max(dense.values(), default=0.0)
    max_kw = max(keyword.values(), default=0.0)
    fused: dict[str, float] = {}
    for cid in dense.keys() | keyword.keys():
        d = (dense[cid] + 1) / (max_sim + 1) if cid in dense and max_sim > -1 else 0.0
        k = keyword[cid] / max_kw if cid in keyword and max_kw > 0 else 0.0
        fused[cid] = alpha * d + (1 - alpha) * k
    return fused


def allot_slots(
    total: int, module_share: float, relevant_module: int, relevant_reference: int, available_module: int, available_reference: int
) -> tuple[int, int]:
    """Module and book slots. Slots a group cannot fill with relevant chunks go to the other group only if it has more relevant chunks than its share."""
    m = round(total * module_share)
    r = total - m
    module, reference = m, r
    free_m, free_r = m - min(m, relevant_module), r - min(r, relevant_reference)  # slots a group cannot fill with relevant chunks
    # They move only to a group that has more relevant chunks than its own share, so no slot goes to irrelevant chunks.
    if relevant_reference > r:
        module, reference = module - free_m, reference + free_m
    if relevant_module > m:
        module, reference = module + free_r, reference - free_r
    module, reference = min(module, available_module), min(reference, available_reference)
    # Slots the other group could not take go back to whoever still has chunks to show (hits below the floor are cut later).
    spare = min(total, available_module + available_reference) - module - reference
    if spare > 0:
        extra = min(spare, available_module - module)
        module += extra
        reference += min(spare - extra, available_reference - reference)
    return module, reference


class HybridSearcher:
    def __init__(self, settings: Settings, chunks: ChunksRepo, store: VectorStore, embedder: Embedder, reranker: Reranker | None):
        self._settings = settings
        self._chunks = chunks
        self._store = store
        self._embedder = embedder
        self._reranker = reranker

    def search(self, query: str, course_id: int, filters: SearchFilters = SearchFilters(), total: int | None = None) -> SearchResult:
        total = self._settings.search_results if total is None else total
        alpha = self._settings.hybrid_alpha
        use_rerank = self._settings.rerank_enabled and self._reranker is not None
        ms = dict.fromkeys(("embed", "dense", "keyword", "fusion", "rerank"), 0.0)
        started = time.perf_counter()

        def timed(key: str, since: float) -> None:
            ms[key] += (time.perf_counter() - since) * 1000

        chunk_ids = None
        if filters.topic_id is not None:
            chunk_ids = [c.id for c in self._chunks.topic_chunks(filters.topic_id, filters.module_id, course_id)]
        keyword_filters = KeywordFilters(filters.module_id, filters.topic_id, filters.file_id, filters.kind)

        t = time.perf_counter()
        vector = self._embedder.embed_query(query)
        timed("embed", t)

        ranked: dict[Origin, list[Hit]] = {}
        relevant: dict[Origin, int] = {}
        rerank_in = 0
        for origin in ORIGINS:
            t = time.perf_counter()
            dense = {
                h.chunk_id: h.similarity
                for h in self._store.query(
                    vector, course_id, origin, module_id=filters.module_id, file_id=filters.file_id,
                    kind=filters.kind, chunk_ids=chunk_ids, k=SHORTLIST,
                )
            }
            timed("dense", t)
            t = time.perf_counter()
            keyword = dict(self._chunks.keyword_search(query, course_id, origin, keyword_filters, SHORTLIST))
            timed("keyword", t)

            t = time.perf_counter()
            fused = tm2c2(dense, keyword, alpha)
            top = sorted(fused, key=lambda c: (-fused[c], c))[:SHORTLIST]
            timed("fusion", t)
            # A chunk deleted since indexing is skipped; the course/origin check is a second guard on the vector store's filter.
            found = {c.id: c for c in self._chunks.get_many(top) if c.course_id == course_id and c.origin == origin}
            if len(found) < len(top):
                log.info("search skipped %d stale or foreign chunks (%s)", len(top) - len(found), origin)
            top = [c for c in top if c in found]

            scores: list[float | None] = [None] * len(top)
            if use_rerank and top:
                t = time.perf_counter()
                scores = list(self._reranker.score(query, [_rerank_text(found[c]) for c in top]))
                timed("rerank", t)
                rerank_in += len(top)
            hits = [
                Hit(found[c], origin, dense.get(c, 0.0), keyword.get(c, 0.0), fused[c], s) for c, s in zip(top, scores)
            ]
            if use_rerank:
                hits.sort(key=lambda h: (-h.rerank, -h.fused, h.chunk.id))
                relevant[origin] = sum(h.rerank >= RERANK_RELEVANT_MIN for h in hits)
            else:
                relevant[origin] = len(hits)
            ranked[origin] = hits

        m, r = allot_slots(
            total, self._settings.search_module_share, relevant["module"], relevant["reference"],
            len(ranked["module"]), len(ranked["reference"]),
        )
        hits = ranked["module"][:m] + ranked["reference"][:r]
        # With the reranker off, fused scores are normalised per origin, so the order across origins is only approximate.
        hits.sort(key=lambda h: (-(h.rerank if use_rerank else h.fused), h.chunk.id))
        cut = 0
        if use_rerank:
            passing = [h for h in hits if h.rerank >= RERANK_RELEVANT_MIN]
            cut = len(hits) - len(passing)
            if not passing:
                best = sorted(ranked["module"] + ranked["reference"], key=lambda h: (-h.rerank, -h.fused, h.chunk.id))
                passing = [replace(h, weak=True) for h in best[:WEAK_FALLBACK]]
            hits = passing
        ms["total"] = (time.perf_counter() - started) * 1000
        trace = {
            "query": query,
            "filters": asdict(filters),
            "alpha": alpha,
            "reranker": use_rerank,
            "k": {"dense": SHORTLIST, "keyword": SHORTLIST, "rerank_in": rerank_in, "returned": len(hits)},
            "slots": {"module": m, "reference": r},
            "cut": cut,
            "ms": {k: round(v, 1) for k, v in ms.items()},
            "chunks": [
                {
                    "id": h.chunk.id, "origin": h.origin, "dense": round(h.dense, 3), "keyword": round(h.keyword, 3),
                    "fused": round(h.fused, 3), "rerank": None if h.rerank is None else round(h.rerank, 3),
                    "weak": h.weak,
                }
                for h in hits
            ],
        }
        log.info("search course=%s returned=%d cut=%d slots=%d/%d total_ms=%.0f", course_id, len(hits), cut, m, r, ms["total"])
        log.debug("search query=%r chunks=%s", query, [h.chunk.id for h in hits])
        return SearchResult(hits, trace)


def _rerank_text(chunk: StoredChunk) -> str:
    return f"{chunk.heading_path}\n{chunk.text}" if chunk.heading_path else chunk.text
