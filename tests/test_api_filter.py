# Offline tests for the filter logic — no network, runs in milliseconds.
# python -m pytest tests/ -q

from stardown.api import filter_repos

SAMPLE = [
    {"full_name": "a/fast-py", "description": "fast python tool", "language": "Python",
     "topics": ["cli", "speed"], "fork": False, "archived": False},
    {"full_name": "b/web-js", "description": "web thing", "language": "JavaScript",
     "topics": ["web"], "fork": True, "archived": False},
    {"full_name": "c/old-py", "description": "archived demo", "language": "Python",
     "topics": ["demo"], "fork": False, "archived": True},
]


def test_language_filter_ci():
    got = filter_repos(SAMPLE, language="python")
    assert {r["full_name"] for r in got} == {"a/fast-py", "c/old-py"}


def test_topic_filter_ci():
    got = filter_repos(SAMPLE, topic="CLI")
    assert [r["full_name"] for r in got] == ["a/fast-py"]


def test_query_matches_name_or_desc():
    assert [r["full_name"] for r in filter_repos(SAMPLE, query="WEB")] == ["b/web-js"]
    assert [r["full_name"] for r in filter_repos(SAMPLE, query="fast")] == ["a/fast-py"]


def test_exclude_forks_and_archived():
    got = filter_repos(SAMPLE, include_forks=False, include_archived=False)
    assert [r["full_name"] for r in got] == ["a/fast-py"]
