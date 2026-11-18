import pytest
from solution import LRUCache


@pytest.mark.parametrize("capacity", [0, -1])
def test_capacity_must_be_at_least_one(capacity):
    with pytest.raises(ValueError):
        LRUCache(capacity)


def test_put_then_get():
    cache = LRUCache(2)
    assert cache.put("a", 1) is None
    assert cache.get("a") == 1
    assert len(cache) == 1


def test_get_missing_returns_the_default():
    cache = LRUCache(2)
    assert cache.get("nope") is None
    assert cache.get("nope", 42) == 42
    assert len(cache) == 0
    assert "nope" not in cache


def test_least_recently_used_key_is_evicted():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.put("c", 3) == "a"
    assert "a" not in cache
    assert cache.keys() == ["b", "c"]


def test_get_refreshes_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")
    assert cache.put("c", 3) == "b"
    assert cache.keys() == ["a", "c"]


def test_updating_a_key_refreshes_recency_and_evicts_nothing():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.put("a", 10) is None
    assert len(cache) == 2
    assert cache.put("c", 3) == "b"
    assert cache.get("a") == 10


def test_contains_does_not_refresh_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert "a" in cache
    assert cache.put("c", 3) == "a"


def test_peek_does_not_refresh_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.peek("a") == 1
    assert cache.peek("zzz", "fallback") == "fallback"
    assert cache.put("c", 3) == "a"


def test_get_of_a_missing_key_does_not_change_order():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("missing")
    assert cache.keys() == ["a", "b"]


def test_keys_run_from_least_to_most_recently_used():
    cache = LRUCache(3)
    for key in ("a", "b", "c"):
        cache.put(key, key.upper())
    cache.get("a")
    cache.put("b", "B2")
    assert cache.keys() == ["c", "a", "b"]


def test_delete():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.delete("a") is True
    assert cache.delete("a") is False
    assert len(cache) == 1
    assert cache.put("c", 3) is None  # room was freed, so nothing is evicted
    assert cache.keys() == ["b", "c"]


def test_falsy_and_none_values_are_real_values():
    cache = LRUCache(3)
    cache.put("zero", 0)
    cache.put("empty", "")
    cache.put("none", None)
    assert cache.get("zero", "default") == 0
    assert cache.get("empty", "default") == ""
    assert cache.get("none", "default") is None
    assert cache.peek("none", "default") is None


def test_capacity_one():
    cache = LRUCache(1)
    cache.put("a", 1)
    assert cache.put("b", 2) == "a"
    assert cache.put("b", 3) is None
    assert cache.keys() == ["b"]
    assert cache.get("b") == 3


def test_long_sequence_keeps_only_the_newest_entries():
    cache = LRUCache(3)
    evicted = [cache.put(i, i * i) for i in range(10)]
    assert evicted == [None, None, None, 0, 1, 2, 3, 4, 5, 6]
    assert cache.keys() == [7, 8, 9]
    assert len(cache) == 3
