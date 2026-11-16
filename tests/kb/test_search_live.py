"""Live check of hybrid search: real Ollama embeddings, a real `chroma run` server and the real reranker.

Prints a markdown report (saved as search_calibration.md). The fixture text is written here, not course material.
Run: uv run pytest -m "ollama and models" tests/kb/test_search_live.py -s
"""

from pathlib import Path

import pytest

from eduagent.config import Settings
from eduagent.db.chunks import ChunksRepo, StoredChunk
from eduagent.db.courses import CoursesRepo
from eduagent.db.database import Database
from eduagent.db.files import FilesRepo
from eduagent.kb import search as search_module
from eduagent.kb.embed import Embedder
from eduagent.kb.rerank import Reranker
from eduagent.kb.search import HybridSearcher
from eduagent.kb.store import VectorStore

pytestmark = [pytest.mark.ollama, pytest.mark.models]

SLIDES = [
    ("Decision Trees: Overview", "A decision tree predicts a label by asking a sequence of yes/no questions about the features, starting at the root and ending at a leaf."),
    ("Splitting a Node", "At each node we try every feature and threshold and keep the split that makes the child nodes as pure as possible."),
    ("Gini index", "The Gini index of a node is one minus the sum of the squared class proportions. A node with only one class has a Gini index of zero."),
    ("Entropy and Information Gain", "Entropy measures the disorder of a node. Information gain is the entropy of the parent minus the weighted entropy of its children."),
    ("Choosing the Best Split", "We compute the weighted impurity of the two children for every candidate split and pick the lowest. Ties are broken by feature order."),
    ("Stopping Rules", "We stop splitting a node when it reaches max_depth, when it holds fewer than min_samples_split samples, or when no split lowers the impurity."),
    ("Overfitting in Trees", "A tree grown until every leaf is pure memorises the training set and does badly on new data."),
    ("Cost-Complexity Pruning", "Pruning removes the branches that add little. We minimise the training error plus alpha times the number of leaves, and pick alpha by validation."),
    ("Splitting the Data in Python", "Hold out a test set first: X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0). Never fit on the test part."),
    ("Regression Trees", "A regression tree predicts the mean of the training targets in a leaf and chooses splits that reduce the squared error."),
    ("Strengths and Weaknesses", "Trees are easy to read and need no feature scaling, but small changes in the data can produce a very different tree."),
    ("Summary", "Grow a tree by greedy splits, control its size with stopping rules or pruning, and always evaluate on held-out data."),
]

# (topic, four facts); every fact becomes one book page, so each topic spans four pages.
BOOK = [
    ("Bias-variance tradeoff", [
        "The expected test error of a model splits into squared bias, variance and irreducible noise.",
        "Flexible methods have low bias but high variance, because they change a lot from one training sample to another.",
        "Rigid methods have high bias and low variance, so they miss real structure but are stable.",
        "The best test error comes from a model whose flexibility balances bias against variance, which we find by validation.",
    ]),
    ("Ridge regression", [
        "Ridge regression minimises the residual sum of squares plus lambda times the sum of squared coefficients.",
        "As lambda grows the ridge coefficients shrink toward zero, but they never become exactly zero.",
        "Predictors should be standardised before ridge regression, since the penalty depends on their scale.",
        "Ridge reduces variance at the cost of a little bias, and lambda is chosen by cross-validation.",
    ]),
    ("Lasso", [
        "The lasso penalises the sum of absolute coefficient values, which can set some coefficients exactly to zero.",
        "Because of that the lasso performs variable selection and gives sparse, easier to interpret models.",
        "The lasso tends to beat ridge when only a few predictors truly matter.",
        "A good lasso penalty is found by cross-validation over a grid of values.",
    ]),
    ("Cross-validation", [
        "In k-fold cross-validation the data is split into k parts, each used once as the validation set.",
        "Leave-one-out cross-validation is the case k equals n and is nearly unbiased but slow.",
        "Five or ten folds give a good balance between bias and variance of the error estimate.",
        "All preprocessing must be repeated inside each fold, or the error estimate will be too optimistic.",
    ]),
    ("Linear regression", [
        "Simple linear regression models the response as an intercept plus a slope times one predictor.",
        "The least squares estimates minimise the sum of the squared residuals.",
        "The standard error of a coefficient tells us how much it would vary across training samples.",
        "R squared is the share of the variance in the response that the model explains.",
    ]),
    ("Logistic regression", [
        "Logistic regression models the log odds of a class as a linear function of the predictors.",
        "The coefficients are estimated by maximum likelihood rather than least squares.",
        "The predicted probability is passed through a threshold to give a class.",
        "With more than two classes we use the multinomial extension of logistic regression.",
    ]),
    ("Support vector machines", [
        "A support vector machine finds the hyperplane with the largest margin between two classes.",
        "Only the observations closest to the margin, the support vectors, determine the hyperplane.",
        "Kernels let the machine form non-linear boundaries without computing the new features.",
        "The cost parameter controls how many margin violations are allowed.",
    ]),
    ("Principal components", [
        "The first principal component is the direction in which the data varies the most.",
        "Each later component is orthogonal to the earlier ones and captures the most remaining variance.",
        "Variables should be scaled to unit variance before computing principal components.",
        "A scree plot shows how much variance each component explains and helps to choose how many to keep.",
    ]),
    ("Clustering", [
        "K-means assigns each point to the nearest of k centroids and then moves each centroid to its cluster mean.",
        "The result depends on the starting centroids, so the algorithm is run from many random starts.",
        "Hierarchical clustering builds a dendrogram that can be cut at any height to give clusters.",
        "The choice of linkage, such as complete or average, changes the shape of the clusters found.",
    ]),
    ("Bootstrap and bagging", [
        "The bootstrap draws samples with replacement from the data to measure the variability of an estimate.",
        "Bagging fits a model to many bootstrap samples and averages their predictions.",
        "Averaging lowers variance, which helps most for high-variance methods such as deep trees.",
        "Out-of-bag observations give a free estimate of test error without a separate validation set.",
    ]),
]

# (question, expectation, ids that a reader would call relevant (for calibration))
QUESTIONS = [
    ("What stopping rules decide when to stop splitting a node?", "module", {"slide-6"}),
    ("How do we prune a tree and how is alpha chosen?", "module", {"slide-8"}),
    ("What is the bias-variance tradeoff?", "book", {"book-Bias-variance tradeoff"}),
    ("How does ridge regression shrink the coefficients?", "book", {"book-Ridge regression"}),
    ("train_test_split", "term", {"slide-9"}),
    ("Gini index", "term", {"slide-3"}),
]


def _ingest(tmp_path, port):
    settings = Settings(_env_file=None, data_dir=tmp_path, chroma_port=port, models_dir=Path(__file__).resolve().parents[2] / "data" / "models")
    db = Database(tmp_path / "study.db")
    db.migrate()
    course = CoursesRepo(db)
    course_id = course.create_course("Machine Learning").id
    module_id = course.add_module(course_id, "Decision Trees")
    files = FilesRepo(db)
    deck = files.add(course_id, module_id, "module", "pptx", "Decision Trees", "trees.pptx", None, "h1")
    book = files.add(course_id, None, "reference", "pdf", "Statistical Learning", "sl.pdf", None, "h2")
    chunks_repo, store, embedder = ChunksRepo(db), VectorStore(port), Embedder(settings)
    store._client.delete_collection(VectorStore.COLLECTION)
    store = VectorStore(port)

    chunks, labels = [], {}
    for n, (title, body) in enumerate(SLIDES, 1):
        cid = f"f{deck.id}-0000-{n:03d}"
        labels[cid] = f"slide-{n}"
        chunks.append(StoredChunk(cid, deck.id, course_id, module_id, "module", "source", n, body, title, "slide", n, n, len(body.split())))
    page = 0
    for topic, facts in BOOK:
        for fact in facts:
            page += 1
            cid = f"f{book.id}-0000-{page:03d}"
            labels[cid] = f"book-{topic}"
            text = f"{topic}. {fact}"
            chunks.append(StoredChunk(cid, book.id, course_id, None, "reference", "source", page, text, f"Chapter: {topic}", "page", page, page, len(text.split())))
    chunks_repo.upsert(chunks)
    vectors = embedder.embed_documents([f"{c.heading_path}\n{c.text}" for c in chunks])
    store.upsert(chunks[: len(SLIDES)], vectors[: len(SLIDES)], 1)
    store.upsert(chunks[len(SLIDES):], vectors[len(SLIDES):], 1)
    return settings, chunks_repo, store, embedder, course_id, labels


def test_live_hybrid_search(tmp_path, chroma_port):
    settings, chunks_repo, store, embedder, course_id, labels = _ingest(tmp_path, chroma_port)
    searcher = HybridSearcher(settings, chunks_repo, store, embedder, Reranker(settings))
    searcher.search("warm up", course_id)  # loads the models; excluded from the timings below

    print("\n# Search calibration (live)\n")
    print(f"Fixtures: {len(SLIDES)}-slide Decision Trees deck (module) and a {len(BOOK) * 4}-page Statistical Learning book (reference).")
    print(f"RERANK_RELEVANT_MIN in force: {search_module.RERANK_RELEVANT_MIN}\n")
    relevant_scores, other_scores = [], []
    outcomes = []
    for question, kind, relevant in QUESTIONS:
        result = searcher.search(question, course_id)
        t = result.trace
        print(f"## {question!r} ({kind})\n")
        print(f"slots {t['slots']} | ms {t['ms']}\n")
        print("| # | chunk | origin | dense | keyword | fused | rerank |\n|---|---|---|---|---|---|---|")
        for i, c in enumerate(t["chunks"], 1):
            print(f"| {i} | {labels[c['id']]} | {c['origin']} | {c['dense']} | {c['keyword']} | {c['fused']} | {c['rerank']} |")
        print()
        # calibration: rerank every chunk of both groups for this question
        everything = chunks_repo.get_many(list(labels))
        scores = Reranker(settings).score(question, [f"{c.heading_path}\n{c.text}" for c in everything])
        for c, s in zip(everything, scores):
            (relevant_scores if labels[c.id] in relevant else other_scores).append((s, labels[c.id], question))
        mine = [s for c, s in zip(everything, scores) if labels[c.id] in relevant]
        rest = [s for c, s in zip(everything, scores) if labels[c.id] not in relevant]
        print(f"Calibration: relevant chunks score {min(mine):.2f}..{max(mine):.2f}; all other chunks score up to {max(rest):.2f}\n")
        origins = [h.origin for h in result.hits]
        top3 = [labels[h.chunk.id] for h in result.hits[:3]]
        if kind == "module":
            outcomes.append((question, origins[0] == "module", f"first hit origin {origins[0]}"))
        elif kind == "book":
            outcomes.append((question, origins.count("reference") >= 7, f"{origins.count('reference')} book chunks"))
        else:
            outcomes.append((question, next(iter(relevant)) in top3, f"top 3 {top3}"))
    print("## Calibration summary\n")
    print(f"Lowest relevant rerank score: {min(relevant_scores)[0]:.2f} ({min(relevant_scores)[1]})")
    print(f"Highest other rerank score: {max(other_scores)[0]:.2f} ({max(other_scores)[1]} for {max(other_scores)[2]!r})\n")
    print("## Outcomes\n")
    for question, ok, detail in outcomes:
        print(f"- {'OK' if ok else 'FAIL'}: {question!r}: {detail}")
    assert all(ok for _, ok, _ in outcomes), [o for o in outcomes if not o[1]]
