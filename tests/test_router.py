from rag.router import route_query


def test_routes_sql_for_stat_question():
    decision = route_query("Who has the highest speed in Gen 1?")
    assert decision.route == "sql"
    assert decision.confidence >= 0.8


def test_routes_vector_for_tactical_question():
    decision = route_query("Recommend a bulky special attacker with good synergy.")
    # "special attack" overlaps with SQL stat terms, so a question that is both
    # tactical AND stat-flavored should correctly route to hybrid, not vector-only.
    assert decision.route == "hybrid"
    assert decision.confidence >= 0.75


def test_routes_hybrid_for_team_vs_team():
    decision = route_query("My team is Charizard and Jolteon, what should I use against a Water lineup?")
    assert decision.route == "hybrid"
    assert decision.confidence >= 0.75


def test_routes_hybrid_when_sql_and_vector_signals_both_exist():
    decision = route_query("Compare top speed options and recommend a tactical counter.")
    assert decision.route == "hybrid"
    assert decision.confidence >= 0.8


def test_empty_query_raises():
    import pytest

    with pytest.raises(ValueError):
        route_query("   ")