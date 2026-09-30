"""Bloom Filter and Cuckoo Filter for fast resource key membership testing."""
from __future__ import annotations

import hashlib
import math
import random
from typing import Any, List


class BloomFilter:
    """Standard Bloom Filter with configurable size and hash functions."""

    def __init__(self, capacity: int = 10000, error_rate: float = 0.01):
        self.capacity = capacity
        self.error_rate = error_rate
        # Calculate optimal size (m) and number of hash functions (k)
        self.size = int(-1 * capacity * math.log(error_rate) / (math.log(2) ** 2))
        self.size = max(self.size, 64)
        self.num_hashes = max(int((self.size / capacity) * math.log(2)), 1)
        self.bit_array = [False] * self.size
        self._count = 0

    def _hashes(self, item: str) -> List[int]:
        indexes = []
        item_bytes = str(item).encode("utf-8")
        h1 = int(hashlib.sha256(item_bytes).hexdigest(), 16)
        h2 = int(hashlib.md5(item_bytes).hexdigest(), 16)
        for i in range(self.num_hashes):
            combined = (h1 + i * h2) % self.size
            indexes.append(combined)
        return indexes

    def add(self, item: str) -> None:
        """Add an item to the Bloom filter."""
        for idx in self._hashes(item):
            self.bit_array[idx] = True
        self._count += 1

    def contains(self, item: str) -> bool:
        """Return True if item might be in set; False if definitely NOT in set."""
        return all(self.bit_array[idx] for idx in self._hashes(item))

    def __contains__(self, item: str) -> bool:
        return self.contains(item)

    def count(self) -> int:
        return self._count


class CuckooFilter:
    """Cuckoo Filter for dynamic set membership checking."""

    def __init__(self, capacity: int = 1000, bucket_size: int = 4, fingerprint_size: int = 2):
        self.capacity = capacity
        self.bucket_size = bucket_size
        self.num_buckets = max(int(capacity / bucket_size / 0.95), 16)
        self.buckets: List[List[int]] = [[] for _ in range(self.num_buckets)]
        self.fingerprint_size = fingerprint_size
        self._count = 0

    def _fingerprint(self, item: str) -> int:
        h = hashlib.sha256(str(item).encode("utf-8")).digest()
        # Take fingerprint_size bytes as int
        fp = int.from_bytes(h[: self.fingerprint_size], byteorder="big")
        return max(fp, 1)  # Ensure non-zero

    def _hash_index(self, item: str) -> int:
        h = int(hashlib.md5(str(item).encode("utf-8")).hexdigest(), 16)
        return h % self.num_buckets

    def _alt_index(self, index: int, fingerprint: int) -> int:
        fp_bytes = fingerprint.to_bytes(self.fingerprint_size, byteorder="big")
        h = int(hashlib.sha256(fp_bytes).hexdigest(), 16)
        return (index ^ h) % self.num_buckets

    def add(self, item: str) -> bool:
        """Add an item fingerprint to the cuckoo filter."""
        fp = self._fingerprint(item)
        i1 = self._hash_index(item)
        i2 = self._alt_index(i1, fp)

        if len(self.buckets[i1]) < self.bucket_size:
            self.buckets[i1].append(fp)
            self._count += 1
            return True
        if len(self.buckets[i2]) < self.bucket_size:
            self.buckets[i2].append(fp)
            self._count += 1
            return True

        # Cuckoo displacement kick loop
        curr_idx = random.choice([i1, i2])
        for _ in range(50):
            entry_idx = random.randint(0, len(self.buckets[curr_idx]) - 1)
            fp, self.buckets[curr_idx][entry_idx] = self.buckets[curr_idx][entry_idx], fp
            curr_idx = self._alt_index(curr_idx, fp)
            if len(self.buckets[curr_idx]) < self.bucket_size:
                self.buckets[curr_idx].append(fp)
                self._count += 1
                return True
        return False

    def contains(self, item: str) -> bool:
        """Check if an item fingerprint is in bucket i1 or i2."""
        fp = self._fingerprint(item)
        i1 = self._hash_index(item)
        i2 = self._alt_index(i1, fp)
        return fp in self.buckets[i1] or fp in self.buckets[i2]

    def __contains__(self, item: str) -> bool:
        return self.contains(item)
