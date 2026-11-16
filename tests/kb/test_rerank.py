import pytest

from eduagent.config import Settings
from eduagent.kb import rerank
from eduagent.kb.rerank import Reranker


class FakeEncoder:
    instances = []

    def __init__(self, model_name, cache_dir=None, **kwargs):
        self.model_name, self.cache_dir = model_name, cache_dir
        FakeEncoder.instances.append(self)

    def rerank(self, query, documents):
        return iter([float(len(d)) for d in documents])


@pytest.fixture
def fake(monkeypatch):
    FakeEncoder.instances = []
    monkeypatch.setattr(rerank, "TextCrossEncoder", FakeEncoder)
    return FakeEncoder


def test_reranker_uses_models_dir(fake, tmp_path):
    settings = Settings(_env_file=None, models_dir=tmp_path / "models")
    r = Reranker(settings)
    assert fake.instances == []  # lazy
    r.score("q", ["a"])
    [enc] = fake.instances
    assert enc.model_name == "Xenova/ms-marco-MiniLM-L-6-v2"
    assert enc.cache_dir == str(tmp_path / "models" / "fastembed")


def test_score_order_kept_and_model_loaded_once(fake, tmp_path):
    r = Reranker(Settings(_env_file=None, models_dir=tmp_path))
    assert r.score("q", ["aaa", "a", "aa"]) == [3.0, 1.0, 2.0]
    r.score("q", ["b"])
    assert len(fake.instances) == 1


def test_empty_input_does_not_load_model(fake, tmp_path):
    assert Reranker(Settings(_env_file=None, models_dir=tmp_path)).score("q", []) == []
    assert fake.instances == []


GINI = (
    "The Gini index measures how mixed the classes are inside a node of a decision tree. "
    "It equals one minus the sum of the squared class proportions, so a pure node scores zero."
)
KMEANS = (
    "The k-means algorithm groups points into k clusters by repeatedly assigning each point "
    "to its nearest centroid and then moving every centroid to the mean of its points."
)


@pytest.mark.models
def test_live_rerank_prefers_relevant():
    from eduagent.kb.models_dir import configure_model_dirs

    settings = Settings(_env_file=None)
    configure_model_dirs(settings)
    scores = Reranker(settings).score("what is the gini index", [KMEANS, GINI])
    print(f"\nlive rerank: kmeans={scores[0]:.3f} gini={scores[1]:.3f}")
    assert scores[1] > scores[0]
    files = [p for p in (settings.models_dir / "fastembed").rglob("*") if p.is_file()]
    assert any(p.suffix == ".onnx" for p in files)
