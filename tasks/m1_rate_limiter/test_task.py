import pytest
from solution import KeyedRateLimiter, TokenBucket


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


def test_bucket_starts_full(clock):
    bucket = TokenBucket(5, 2, clock)
    assert bucket.tokens == pytest.approx(5.0)
    assert isinstance(bucket.tokens, float)


@pytest.mark.parametrize(("capacity", "rate"), [(0, 1), (-1, 1), (5, 0), (5, -2)])
def test_invalid_settings_are_rejected(clock, capacity, rate):
    with pytest.raises(ValueError):
        TokenBucket(capacity, rate, clock)
    with pytest.raises(ValueError):
        KeyedRateLimiter(capacity, rate, clock)


def test_allow_consumes_until_empty(clock):
    bucket = TokenBucket(3, 1, clock)
    assert [bucket.allow() for _ in range(4)] == [True, True, True, False]
    assert bucket.tokens == pytest.approx(0.0)


def test_refused_call_consumes_nothing(clock):
    bucket = TokenBucket(5, 1, clock)
    assert bucket.allow(4) is True
    assert bucket.allow(2) is False
    assert bucket.tokens == pytest.approx(1.0)
    assert bucket.allow(1) is True


def test_refill_is_continuous(clock):
    bucket = TokenBucket(5, 2, clock)
    assert bucket.allow(5) is True
    clock.now += 0.5
    assert bucket.tokens == pytest.approx(1.0)
    assert bucket.allow() is True
    assert bucket.allow() is False
    clock.now += 0.25
    assert bucket.tokens == pytest.approx(0.5)


def test_refill_never_exceeds_capacity(clock):
    bucket = TokenBucket(5, 2, clock)
    bucket.allow(2)
    clock.now += 3600
    assert bucket.tokens == pytest.approx(5.0)


def test_fractional_cost(clock):
    bucket = TokenBucket(1, 1, clock)
    assert bucket.allow(0.5) is True
    assert bucket.allow(0.5) is True
    assert bucket.allow(0.5) is False


def test_retry_after(clock):
    bucket = TokenBucket(4, 2, clock)
    assert bucket.retry_after() == 0.0
    bucket.allow(4)
    assert bucket.retry_after() == pytest.approx(0.5)
    assert bucket.retry_after(3) == pytest.approx(1.5)
    clock.now += 1.0
    assert bucket.retry_after(3) == pytest.approx(0.5)
    assert bucket.retry_after(2) == 0.0


def test_retry_after_does_not_consume(clock):
    bucket = TokenBucket(2, 1, clock)
    bucket.retry_after(2)
    bucket.retry_after(1)
    assert bucket.tokens == pytest.approx(2.0)


@pytest.mark.parametrize("cost", [0, -1, 5.5])
def test_invalid_cost_is_rejected(clock, cost):
    bucket = TokenBucket(5, 1, clock)
    with pytest.raises(ValueError):
        bucket.allow(cost)
    with pytest.raises(ValueError):
        bucket.retry_after(cost)
    assert bucket.tokens == pytest.approx(5.0)


def test_cost_equal_to_capacity_is_allowed(clock):
    bucket = TokenBucket(5, 1, clock)
    assert bucket.allow(5) is True


def test_clock_going_backwards_adds_nothing_and_is_not_double_counted(clock):
    bucket = TokenBucket(10, 2, clock)
    bucket.allow(10)
    clock.now = 90.0  # earlier than a time already seen
    assert bucket.tokens == pytest.approx(0.0)
    clock.now = 100.5  # half a second past the latest time seen
    assert bucket.tokens == pytest.approx(1.0)


def test_keys_have_independent_buckets(clock):
    limiter = KeyedRateLimiter(2, 1, clock)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False
    assert limiter.allow("bob") is True
    assert limiter.allow("bob", 1) is True
    assert limiter.allow("bob") is False


def test_new_key_starts_full_whenever_it_first_appears(clock):
    limiter = KeyedRateLimiter(3, 1, clock)
    limiter.allow("early", 3)
    clock.now += 50
    assert limiter.allow("late", 3) is True


def test_keyed_limiter_refills(clock):
    limiter = KeyedRateLimiter(2, 4, clock)
    limiter.allow("k", 2)
    assert limiter.allow("k") is False
    clock.now += 0.25
    assert limiter.allow("k") is True


def test_keyed_limiter_rejects_invalid_cost(clock):
    limiter = KeyedRateLimiter(2, 1, clock)
    with pytest.raises(ValueError):
        limiter.allow("k", 0)
    with pytest.raises(ValueError):
        limiter.allow("k", 3)


def test_keys_are_sorted(clock):
    limiter = KeyedRateLimiter(2, 1, clock)
    for key in ("pear", "apple", "fig"):
        limiter.allow(key)
    assert limiter.keys() == ["apple", "fig", "pear"]


def test_evict_idle_removes_only_keys_idle_for_longer(clock):
    limiter = KeyedRateLimiter(2, 1, clock)
    limiter.allow("old")
    clock.now += 10
    limiter.allow("edge")
    clock.now += 5
    limiter.allow("fresh")
    clock.now += 5  # old idle 20s, edge idle exactly 10s, fresh idle 5s
    assert limiter.evict_idle(10) == 1
    assert limiter.keys() == ["edge", "fresh"]
    assert limiter.evict_idle(10) == 0


def test_refused_call_still_counts_as_a_use(clock):
    limiter = KeyedRateLimiter(1, 0.001, clock)
    limiter.allow("k")
    clock.now += 8
    assert limiter.allow("k") is False
    clock.now += 8
    assert limiter.evict_idle(10) == 0
    assert limiter.keys() == ["k"]


def test_evicted_key_comes_back_full(clock):
    limiter = KeyedRateLimiter(2, 0.001, clock)
    limiter.allow("k", 2)
    clock.now += 100
    assert limiter.evict_idle(60) == 1
    assert limiter.keys() == []
    assert limiter.allow("k", 2) is True
