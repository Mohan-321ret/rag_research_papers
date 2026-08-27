"""Tests for the query intelligence pipeline (Module 5)."""

from fastapi.testclient import TestClient

from app.modules.query_intelligence.analyzer import analyze_query
from app.modules.query_intelligence.expansion import expand_entities
from app.modules.query_intelligence.intent import detect_intent
from app.modules.query_intelligence.parser import parse_query
from app.modules.query_intelligence.temporal import detect_temporal

# ---- the specification example --------------------------------------------


def test_spec_example_end_to_end() -> None:
    structured = analyze_query("What was the leave policy before 2024?", [])

    assert structured.original_query == "What was the leave policy before 2024?"
    assert structured.intent.value == "factual_lookup"
    assert "leave policy" in structured.entities
    assert structured.complexity == "simple"
    assert structured.temporal is True
    assert structured.temporal_direction == "before"
    assert structured.target_date == "2024"
    # Expansion produces alternative phrasings like the spec's examples.
    assert "employee leave" in structured.expanded_query
    assert any("rules" in e or "vacation" in e for e in structured.expanded_query)


def test_knowledge_base_entities_take_priority() -> None:
    structured = analyze_query(
        "what does the annual leave policy say", ["Annual Leave Policy", "FAISS"]
    )
    assert structured.entities[0] == "annual leave policy"


# ---- parser ----------------------------------------------------------------


def test_parser_normalizes_and_extracts_keywords() -> None:
    parsed = parse_query("  What IS the Remote-Work policy?! ")
    assert parsed.normalized == "what is the remote-work policy"
    assert parsed.question_word == "what"
    assert "remote-work" in parsed.keywords
    assert "what" not in parsed.keywords


# ---- intent ----------------------------------------------------------------


def test_intent_detection_variants() -> None:
    cases = {
        "What is the leave policy?": "factual_lookup",
        "How do I submit an expense report?": "procedural",
        "Compare the old and new leave policies": "comparative",
        "Why did the security budget increase?": "analytical",
        "Summarize the HR handbook": "summarization",
    }
    for query, expected in cases.items():
        assert detect_intent(parse_query(query)).value == expected, query


# ---- temporal --------------------------------------------------------------


def test_temporal_detection_variants() -> None:
    before = detect_temporal("what was the policy before 2024")
    assert (before.is_temporal, before.direction, before.target_date) == (True, "before", "2024")

    after = detect_temporal("changes since january 2023")
    assert (after.is_temporal, after.direction, after.target_date) == (True, "after", "2023-01")

    at = detect_temporal("the budget in 2022")
    assert (at.direction, at.target_date) == ("at", "2022")

    current = detect_temporal("what is the current leave policy")
    assert (current.is_temporal, current.direction) == (True, "current")

    past = detect_temporal("what did the policy used to say")
    assert (past.is_temporal, past.direction, past.target_date) == (True, "past", None)

    none = detect_temporal("what is the leave policy")
    assert none.is_temporal is False


# ---- complexity ------------------------------------------------------------


def test_complexity_levels() -> None:
    simple = analyze_query("What is the leave policy?", [])
    assert simple.complexity == "simple"
    assert simple.sub_queries == []

    complex_q = analyze_query(
        "Compare the leave policy and the remote work policy and explain why "
        "the security budget changed between departments over the years",
        [],
    )
    assert complex_q.complexity == "complex"
    assert len(complex_q.sub_queries) >= 2


# ---- expansion -------------------------------------------------------------


def test_expansion_generates_synonym_variants() -> None:
    expansions = expand_entities(["leave policy"])
    assert "vacation policy" in expansions
    assert "leave rules" in expansions
    assert "employee leave" in expansions
    assert "leave policy" not in expansions  # originals excluded


def test_expansion_unknown_terms_yield_nothing() -> None:
    assert expand_entities(["xyzzy frobnicator"]) == []


# ---- API -------------------------------------------------------------------


def test_analyze_endpoint(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/api/v1/chat/analyze",
        headers=auth_headers,
        json={"query": "What was the leave policy before 2024?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "factual_lookup"
    assert "leave policy" in body["entities"]
    assert body["temporal"] is True
    assert body["target_date"] == "2024"
    assert body["expanded_query"]


def test_analyze_requires_auth(client: TestClient) -> None:
    assert client.post("/api/v1/chat/analyze", json={"query": "x"}).status_code == 401


def test_chat_response_includes_analysis(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"query": "How do I submit an expense report?"},
    )
    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["intent"] == "procedural"
    assert analysis["original_query"] == "How do I submit an expense report?"
