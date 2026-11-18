"""Reference solution. Never shown to a model."""


def _check_settings(capacity, refill_per_second):
    if capacity <= 0 or refill_per_second <= 0:
        raise ValueError("capacity and refill_per_second must be positive")


class TokenBucket:
    def __init__(self, capacity, refill_per_second, clock):
        _check_settings(capacity, refill_per_second)
        self._capacity = float(capacity)
        self._rate = float(refill_per_second)
        self._clock = clock
        self._tokens = self._capacity
        self._last = clock()

    def _refill(self):
        now = self._clock()
        if now > self._last:
            self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._rate)
            self._last = now

    def _check_cost(self, cost):
        if cost <= 0 or cost > self._capacity:
            raise ValueError("cost must be positive and no larger than capacity")

    @property
    def tokens(self):
        self._refill()
        return self._tokens

    def allow(self, cost=1.0):
        self._check_cost(cost)
        self._refill()
        if self._tokens >= cost:
            self._tokens -= cost
            return True
        return False

    def retry_after(self, cost=1.0):
        self._check_cost(cost)
        self._refill()
        missing = cost - self._tokens
        return missing / self._rate if missing > 0 else 0.0


class KeyedRateLimiter:
    def __init__(self, capacity, refill_per_second, clock):
        _check_settings(capacity, refill_per_second)
        self._capacity = capacity
        self._rate = refill_per_second
        self._clock = clock
        self._buckets = {}
        self._last_used = {}

    def allow(self, key, cost=1.0):
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(self._capacity, self._rate, self._clock)
        self._last_used[key] = self._clock()
        return self._buckets[key].allow(cost)

    def keys(self):
        return sorted(self._buckets)

    def evict_idle(self, max_idle_seconds):
        now = self._clock()
        idle = [key for key, used in self._last_used.items() if now - used > max_idle_seconds]
        for key in idle:
            del self._buckets[key]
            del self._last_used[key]
        return len(idle)
