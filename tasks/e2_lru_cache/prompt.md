# LRU cache

Write a Python module with a class `LRUCache`: a key-value cache with a fixed capacity that evicts the least recently used entry when it is full.

## `LRUCache(capacity)`

`capacity` is the maximum number of entries. Raise `ValueError` if it is less than 1.

"Using" a key means reading it with `get` or writing it with `put`. The most recently used key is the last one that was used.

## Methods

### `get(key, default=None)`

Returns the value stored for `key` and marks the key as most recently used. If the key is missing, returns `default` and changes nothing. A stored value of `None` is returned as `None`, not as the default.

### `put(key, value)`

Stores the value and marks the key as most recently used. If the key already exists, its value is replaced and nothing is evicted. If adding a new key takes the cache over capacity, the least recently used key is evicted.

Returns the evicted key, or `None` if nothing was evicted.

### `peek(key, default=None)`

Like `get`, but does not change which key is most recently used.

### `delete(key)`

Removes the key. Returns `True` if it was present and `False` otherwise.

### `keys()`

Returns a list of the keys, ordered from least recently used to most recently used.

### `len(cache)` and `key in cache`

`len` returns the number of entries. `in` reports whether a key is present and does not change which key is most recently used.

## Requirements

- Put everything in one module. It will be saved as `solution.py` and imported by a pytest file you cannot see.
- Use only the Python standard library. The code runs on Python 3.12 with no network access.
- Use exactly the names and signatures above.
