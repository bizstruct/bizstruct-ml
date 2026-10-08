"""The temporary ml-side structural validation of Patterns: each check has a failing and a passing case."""
import pytest

from bizstruct_ml.stages.patterns_validation import components, validate_patterns_structure

A3 = ["S1", "S2", "S3"]


def scores(*rows: tuple[str, str, int, int]):
    return list(rows)


ALL_PAIRS_LINKED = scores(("S1", "S2", 3, 0), ("S1", "S3", 2, 0), ("S2", "S3", 2, -1))


# -- 1. every unordered pair exactly once ----------------------------------------------------------


def test_every_pair_once_passes_in_any_order_and_direction():
    validate_patterns_structure(A3, scores(("S3", "S2", 2, -1), ("S2", "S1", 3, 0), ("S3", "S1", 2, 0)), [["S1", "S2", "S3"]])


def test_a_missing_pair_is_named():
    with pytest.raises(ValueError, match="missing the pairs S2-S3"):
        validate_patterns_structure(A3, scores(("S1", "S2", 3, 0), ("S1", "S3", 2, 0)), [["S1", "S2", "S3"]])


def test_a_pair_scored_twice_is_named_even_when_written_reversed():
    with pytest.raises(ValueError, match="more than once: S1-S2"):
        validate_patterns_structure(A3, [*ALL_PAIRS_LINKED, ("S2", "S1", 3, 0)], [["S1", "S2", "S3"]])


def test_an_unknown_alias_in_a_pair_is_named():
    with pytest.raises(ValueError, match="unknown alias 'S9'"):
        validate_patterns_structure(A3, [*ALL_PAIRS_LINKED, ("S1", "S9", 1, 0)], [["S1", "S2", "S3"]])


def test_a_single_segment_has_no_pairs_and_any_pair_is_unknown():
    validate_patterns_structure(["S1"], [], [["S1"]])
    with pytest.raises(ValueError, match="unknown alias"):
        validate_patterns_structure(["S1"], [("S1", "S2", 1, 0)], [["S1"]])


# -- 2. every alias in exactly one group -----------------------------------------------------------


def test_an_alias_in_no_group_is_named():
    with pytest.raises(ValueError, match="in no group: S3"):
        validate_patterns_structure(A3, ALL_PAIRS_LINKED, [["S1", "S2"]])


def test_an_alias_in_two_groups_is_named():
    with pytest.raises(ValueError, match="listed more than once in the groups: S2"):
        validate_patterns_structure(A3, ALL_PAIRS_LINKED, [["S1", "S2"], ["S2", "S3"]])


def test_an_alias_repeated_inside_one_group_is_named():
    with pytest.raises(ValueError, match="listed more than once in the groups: S1"):
        validate_patterns_structure(A3, ALL_PAIRS_LINKED, [["S1", "S1", "S2", "S3"]])


def test_an_unknown_alias_in_a_group_is_named():
    with pytest.raises(ValueError, match="groups names the unknown alias 'S7'"):
        validate_patterns_structure(A3, ALL_PAIRS_LINKED, [["S1", "S2", "S3", "S7"]])


def test_an_empty_group_is_reported():
    with pytest.raises(ValueError, match="a group has no aliases"):
        validate_patterns_structure(A3, ALL_PAIRS_LINKED, [["S1", "S2", "S3"], []])


# -- 3. groups equal the connected components ------------------------------------------------------


def test_groups_equal_the_components_when_a_conflict_splits_the_graph():
    split = scores(("S1", "S2", 3, 0), ("S1", "S3", 1, -4), ("S2", "S3", 0, -2))
    validate_patterns_structure(A3, split, [["S1", "S2"], ["S3"]])
    validate_patterns_structure(A3, split, [["S3"], ["S2", "S1"]])  # order of groups and aliases is free


def test_one_group_when_the_split_was_expected_names_both_sides():
    split = scores(("S1", "S2", 3, 0), ("S1", "S3", 1, -4), ("S2", "S3", 0, -2))
    with pytest.raises(ValueError, match=r"components are \[\{S1, S2\}, \{S3\}\], but you wrote \[\{S1, S2, S3\}\]"):
        validate_patterns_structure(A3, split, [["S1", "S2", "S3"]])


def test_a_split_when_the_graph_is_connected_is_an_error():
    with pytest.raises(ValueError, match="connected components"):
        validate_patterns_structure(A3, ALL_PAIRS_LINKED, [["S1", "S2"], ["S3"]])


def test_the_edge_threshold_is_net_score_minus_one_inclusive():
    # net -1 is an edge (joined); net -2 is not
    joined = scores(("S1", "S2", 0, -1))
    apart = scores(("S1", "S2", 0, -2))
    validate_patterns_structure(["S1", "S2"], joined, [["S1", "S2"]])
    validate_patterns_structure(["S1", "S2"], apart, [["S1"], ["S2"]])
    with pytest.raises(ValueError):
        validate_patterns_structure(["S1", "S2"], joined, [["S1"], ["S2"]])
    with pytest.raises(ValueError):
        validate_patterns_structure(["S1", "S2"], apart, [["S1", "S2"]])


def test_components_follow_transitive_edges():
    # S1-S2 and S2-S3 linked, S1-S3 not: still one component
    chain = scores(("S1", "S2", 2, 0), ("S1", "S3", 0, -5), ("S2", "S3", 2, 0))
    validate_patterns_structure(A3, chain, [["S1", "S2", "S3"]])
    assert components(A3, [("S1", "S2"), ("S2", "S3")]) == [["S1", "S2", "S3"]]
    assert components(A3, []) == [["S1"], ["S2"], ["S3"]]


def test_all_problems_are_reported_together():
    with pytest.raises(ValueError) as e:
        validate_patterns_structure(A3, scores(("S1", "S2", 1, 0)), [["S1"]])
    message = str(e.value)
    assert "missing the pairs S1-S3, S2-S3" in message and "in no group: S2, S3" in message
