import pytest

from eduagent.db.courses import CoursesRepo
from eduagent.db.database import Database


@pytest.fixture
def repo(tmp_path):
    db = Database(tmp_path / "study.db")
    db.migrate()
    return CoursesRepo(db)


def test_duplicate_course_rejected(repo):
    repo.create_course("ML")
    with pytest.raises(ValueError):
        repo.create_course("ml")


def test_blank_course_rejected(repo):
    with pytest.raises(ValueError):
        repo.create_course("   ")


def test_list_courses(repo):
    c = repo.create_course("  ML ")
    assert c.name == "ML"
    assert repo.list_courses() == [c]


def test_shared_topic_appears_under_both_modules(repo):
    c = repo.create_course("ML")
    m2 = repo.add_module(c.id, "Module 2")
    m6 = repo.add_module(c.id, "Module 6")
    t = repo.add_topic(c.id, "Gradient Descent")
    repo.link_topic(m2, t)
    repo.link_topic(m6, t)
    nodes = repo.course_map(c.id)
    assert [n.name for n in nodes] == ["Module 2", "Module 6"]
    assert [n.topics[0].id for n in nodes] == [t, t]
    assert nodes[0].topics[0].mastery is None


def test_link_topic_idempotent(repo):
    c = repo.create_course("ML")
    m = repo.add_module(c.id, "M1")
    t = repo.add_topic(c.id, "T")
    repo.link_topic(m, t)
    repo.link_topic(m, t)
    assert len(repo.course_map(c.id)[0].topics) == 1


def test_add_topic_get_or_create(repo):
    c = repo.create_course("ML")
    assert repo.add_topic(c.id, "Gradient Descent") == repo.add_topic(c.id, "gradient descent")


def test_add_module_get_or_create(repo):
    c = repo.create_course("ML")
    assert repo.add_module(c.id, "Module 1") == repo.add_module(c.id, "module 1")
    assert len(repo.course_map(c.id)) == 1


def test_course_map_order_and_empty_module(repo):
    c = repo.create_course("ML")
    m1 = repo.add_module(c.id, "Zeta")
    repo.add_module(c.id, "Alpha")
    for name in ["banana", "Cherry", "apple"]:
        repo.link_topic(m1, repo.add_topic(c.id, name))
    nodes = repo.course_map(c.id)
    assert [n.name for n in nodes] == ["Zeta", "Alpha"]
    assert [t.name for t in nodes[0].topics] == ["apple", "banana", "Cherry"]
    assert nodes[1].topics == []
