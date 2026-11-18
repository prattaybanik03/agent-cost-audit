import pytest
from solution import insert_interval, merge_intervals, total_covered


def test_empty():
    assert merge_intervals([]) == []
    assert total_covered([]) == 0


def test_single_interval_is_returned_as_is():
    assert merge_intervals([(2, 5)]) == [(2, 5)]


def test_overlapping_intervals_merge():
    assert merge_intervals([(1, 4), (2, 6)]) == [(1, 6)]


def test_touching_intervals_merge():
    assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]


def test_adjacent_integers_do_not_merge():
    assert merge_intervals([(1, 2), (3, 4)]) == [(1, 2), (3, 4)]


def test_nested_interval_is_absorbed():
    assert merge_intervals([(1, 10), (3, 4), (5, 6)]) == [(1, 10)]


def test_unsorted_input_is_sorted_in_the_output():
    assert merge_intervals([(8, 9), (1, 2), (4, 6), (5, 7)]) == [(1, 2), (4, 7), (8, 9)]


def test_chain_of_overlaps_collapses_to_one():
    assert merge_intervals([(1, 3), (2, 5), (4, 8), (8, 9)]) == [(1, 9)]


def test_duplicates_and_point_intervals():
    assert merge_intervals([(2, 2), (2, 2), (5, 5)]) == [(2, 2), (5, 5)]
    assert merge_intervals([(1, 4), (4, 4)]) == [(1, 4)]


def test_negative_values():
    assert merge_intervals([(-5, -1), (-2, 3), (10, 12)]) == [(-5, 3), (10, 12)]


def test_output_items_are_tuples():
    result = merge_intervals([(1, 2), (2, 3)])
    assert all(isinstance(item, tuple) for item in result)


def test_input_is_not_modified():
    intervals = [(5, 6), (1, 3), (2, 4)]
    snapshot = list(intervals)
    merge_intervals(intervals)
    insert_interval(intervals, (0, 1))
    total_covered(intervals)
    assert intervals == snapshot


def test_start_after_end_is_rejected():
    with pytest.raises(ValueError):
        merge_intervals([(1, 2), (5, 4)])
    with pytest.raises(ValueError):
        total_covered([(3, 1)])


def test_insert_into_a_gap():
    assert insert_interval([(1, 2), (8, 9)], (4, 5)) == [(1, 2), (4, 5), (8, 9)]


def test_insert_that_bridges_several_intervals():
    assert insert_interval([(1, 2), (4, 5), (7, 8), (20, 21)], (2, 7)) == [(1, 8), (20, 21)]


def test_insert_into_empty_list():
    assert insert_interval([], (3, 4)) == [(3, 4)]


def test_insert_handles_unsorted_overlapping_input():
    assert insert_interval([(6, 9), (1, 4), (3, 5)], (10, 11)) == [(1, 5), (6, 9), (10, 11)]


def test_insert_rejects_a_bad_new_interval():
    with pytest.raises(ValueError):
        insert_interval([(1, 2)], (9, 3))


def test_total_covered_counts_overlap_once():
    assert total_covered([(1, 4), (2, 6)]) == 5
    assert total_covered([(1, 2), (3, 4)]) == 2
    assert total_covered([(7, 7)]) == 0
    assert total_covered([(-3, 3), (0, 1), (10, 15)]) == 11
