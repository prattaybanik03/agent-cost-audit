# Token-bucket rate limiter

Write a Python module with two classes: a token bucket, and a rate limiter that keeps one bucket per key.

Time comes from a `clock` argument: a function taking no arguments and returning the current time in seconds as a float. Never read the real time.

## `TokenBucket(capacity, refill_per_second, clock)`

A bucket holds up to `capacity` tokens and gains `refill_per_second` tokens per second, never exceeding `capacity`. It starts full at the time it is created.

Raise `ValueError` if `capacity <= 0` or `refill_per_second <= 0`.

Refill is continuous, so half a second at 2 tokens per second adds 1 token. Before any method below reads or changes the token count, it first adds the tokens earned since the last refill.

If the clock returns a time earlier than one already seen, treat it as no time having passed. Keep the later time as the reference point, so time that has already been counted is never counted twice.

### `tokens` (read-only property)

The current number of tokens, as a float.

### `allow(cost=1.0)`

If at least `cost` tokens are available, removes them and returns `True`. Otherwise returns `False` and removes nothing.

### `retry_after(cost=1.0)`

Returns how many seconds must pass before `cost` tokens are available. Returns `0.0` if they are available now. Does not remove tokens.

`allow` and `retry_after` raise `ValueError` if `cost <= 0` or `cost > capacity`.

## `KeyedRateLimiter(capacity, refill_per_second, clock)`

Keeps a separate `TokenBucket` for each key, all with the same settings. Raises `ValueError` for the same invalid settings as `TokenBucket`.

### `allow(key, cost=1.0)`

Applies `allow(cost)` to that key's bucket and returns the result. A key's bucket is created, full, the first time the key is seen. Every call to `allow` for a key counts as a use of that key, whether or not it is allowed.

### `keys()`

Returns a sorted list of the keys that currently have a bucket.

### `evict_idle(max_idle_seconds)`

Removes every bucket whose key was last used more than `max_idle_seconds` ago and returns how many were removed. A key that has been idle for exactly `max_idle_seconds` is kept. An evicted key that is used again gets a new, full bucket.

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
