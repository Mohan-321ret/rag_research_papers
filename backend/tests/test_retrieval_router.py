"""Unit tests for the deterministic retrieval router (Module 6)."""

from app.modules.query_intelligence.analyzer import analyze_query
from app.modules.retrieval.fusion import reciprocal_rank_fusion
from app.modules.retrieval.router import RetrievalRoute, decide_route

# ---- routing rules ----------------------------------------------------


def _route(query: str) -> RetrievalRoute:
    return decide_route(analyze_query(query, known_entities=[])).route


def test_exact_identifier_routes_to_bm25() -> None:
    assert _route("What does policy POL-4521 say about remote work?") == RetrievalRoute.BM25


def test_clause_reference_routes_to_bm25() -> None:
    assert _route("What is stated in Section 4.2 of the handbook?") == RetrievalRoute.BM25


def test_quoted_phrase_routes_to_bm25() -> None:
    assert _route('Find the exact clause "termination for cause"') == RetrievalRoute.BM25


def test_short_keyword_query_routes_to_bm25() -> None:
    assert _route("annual leave allowance") == RetrievalRoute.BM25


def test_conceptual_question_routes_to_vector() -> None:
    assert _route("What is our approach to employee wellbeing?") == RetrievalRoute.VECTOR


def test_relationship_query_routes_to_graph() -> None:
    assert (
        _route("How is the leave policy related to the remote work policy?")
        == RetrievalRoute.GRAPH
    )


def test_authorship_query_routes_to_graph() -> None:
    assert _route("Who wrote the security policy?") == RetrievalRoute.GRAPH


def test_complex_query_routes_to_hybrid() -> None:
    route = _route(
        "Compare the leave policy and the remote work policy and explain why "
        "the security budget changed between departments over the years"
    )
    assert route == RetrievalRoute.HYBRID


def test_routing_decision_carries_reasons() -> None:
    decision = decide_route(analyze_query("policy POL-99", known_entities=[]))
    assert decision.route == RetrievalRoute.BM25
    assert decision.reasons


# ---- reciprocal rank fusion --------------------------------------------


def test_rrf_favors_items_ranked_by_multiple_retrievers() -> None:
    fused = reciprocal_rank_fusion(
        {
            "vector": ["a", "b", "c"],
            "bm25": ["b", "a", "d"],
        }
    )
    # "a" and "b" appear in both lists and should outrank single-list items.
    top_two = {fused[0].key, fused[1].key}
    assert top_two == {"a", "b"}
    assert set(fused[0].retrievers) | set(fused[1].retrievers) == {"vector", "bm25"}


def test_rrf_single_list_preserves_order() -> None:
    fused = reciprocal_rank_fusion({"vector": ["x", "y", "z"]})
    assert [hit.key for hit in fused] == ["x", "y", "z"]
    assert all(hit.retrievers == ["vector"] for hit in fused)


def test_rrf_empty_input() -> None:
    assert reciprocal_rank_fusion({}) == []


def test_rrf_scores_decrease_monotonically() -> None:
    fused = reciprocal_rank_fusion({"vector": ["a", "b", "c", "d"]})
    scores = [hit.score for hit in fused]
    assert scores == sorted(scores, reverse=True)
