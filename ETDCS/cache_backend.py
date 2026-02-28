# =============================================================================
# cache_backend.py - Abstracted Cache Backend for ETDCS
# Task 15 - Redis Cache Support
# =============================================================================
# Provides a unified caching interface that automatically selects the best
# available backend:
#   - RedisCache: When Redis is available (shared across workers)
#   - MemoryCache: Fallback to in-memory dict (single worker)
#
# Design Pattern: Strategy Pattern with Auto-Detection
#
# Usage:
#   from cache_backend import cache, make_key, TTL_STATS
#
#   key = make_key("stats", project, discipline, station)
#   data = cache.get(key)
#   if data is None:
#       data = compute_expensive_query()
#       cache.set(key, data, TTL_STATS)
#
# Architecture:
#
#                     ┌─────────────────┐
#                     │  CacheBackend   │
#                     │   (abstract)    │
#                     └────────┬────────┘
#                              │
#                ┌─────────────┴─────────────┐
#                │                           │
#         ┌──────▼──────┐             ┌──────▼──────┐
#         │ MemoryCache │             │ RedisCache  │
#         │  (default)  │             │ (if avail)  │
#         └─────────────┘             └─────────────┘
#
# =============================================================================

from __future__ import annotations

import json
import os
import time
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

# =============================================================================
# TTL CONSTANTS (Time To Live in seconds)
# =============================================================================
# Different data types have different cache durations based on:
# - How often the data changes
# - How expensive it is to recompute
# - Business requirements for data freshness

TTL_STATS = 120        # 2 minutes - Statistics change frequently
TTL_TASKS = 300        # 5 minutes - Task progress updates often
TTL_DELIVERABLES = 600 # 10 minutes - Deliverables change less often
TTL_CALENDAR = 300     # 5 minutes - Calendar events moderate change
TTL_DELETED = 60       # 1 minute - Deleted items need quick visibility
TTL_ALERTS = 120       # 2 minutes - Alerts should be fresh
TTL_TIMELINE = 600     # 10 minutes - Timeline data is relatively static

# =============================================================================
# REDIS AVAILABILITY CHECK
# =============================================================================
# Redis is optional - if not installed or not available, fall back to MemoryCache

_REDIS_AVAILABLE = False
_RedisException = None

try:
    import redis
    _REDIS_AVAILABLE = True
except ImportError:
    redis = None  # type: ignore
    _RedisException = Exception  # Fallback for type hints

# =============================================================================
# CONFIGURATION
# =============================================================================

# Redis connection URL from environment (with default)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Key prefix for all ETDCS cache entries (prevents collisions with other apps)
KEY_PREFIX = "etdcs:"

# Separator for building compound keys
KEY_SEPARATOR = ":"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def make_key(prefix: str, *parts: str) -> str:
    """
    Build a consistent cache key from a prefix and multiple parts.

    All parts are converted to strings and joined with the key separator.
    This ensures consistent key formatting across the application.

    Args:
        prefix: Key prefix/category (e.g., "stats", "tasks", "deliverables")
        *parts: Variable number of key components

    Returns:
        Formatted cache key string

    Examples:
        >>> make_key("stats", "Morjan", "HVAC", "All")
        'stats:Morjan:HVAC:All'

        >>> make_key("tasks", "project1", "123")
        'tasks:project1:123'

        >>> make_key("user", "session", "abc123")
        'user:session:abc123'
    """
    # Convert all parts to strings and filter out None/empty values
    str_parts = [str(p) for p in parts if p is not None and str(p).strip()]

    # Join with separator
    return KEY_SEPARATOR.join([prefix] + str_parts)


def _serialize(value: Any) -> str:
    """
    Serialize a value to JSON string for storage.

    Args:
        value: Any JSON-serializable Python object

    Returns:
        JSON string representation

    Raises:
        TypeError: If value is not JSON-serializable
    """
    return json.dumps(value, ensure_ascii=False, default=str)


def _deserialize(data: str) -> Any:
    """
    Deserialize a JSON string back to Python object.

    Args:
        data: JSON string from cache

    Returns:
        Python object (dict, list, int, float, str, bool, or None)
    """
    return json.loads(data)


# =============================================================================
# ABSTRACT BASE CLASS
# =============================================================================

class CacheBackend(ABC):
    """
    Abstract base class for cache backends.

    Defines the interface that all cache implementations must follow.
    This allows the application to switch between different cache backends
    (Memory, Redis, etc.) without changing application code.

    All methods are abstract and must be implemented by subclasses.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Store a value in the cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (default: 5 minutes)
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Remove a specific key from the cache.

        Args:
            key: Cache key to delete
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        Clear all entries from the cache.

        Warning: This affects ALL cached data for this backend.
        Use with caution in production.
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists and is not expired, False otherwise
        """
        pass

    @abstractmethod
    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get the remaining TTL for a key.

        Args:
            key: Cache key

        Returns:
            Remaining seconds, or None if key doesn't exist
        """
        pass


# =============================================================================
# MEMORY CACHE IMPLEMENTATION
# =============================================================================

class MemoryCache(CacheBackend):
    """
    In-memory cache implementation using a dictionary.

    This is the fallback cache backend when Redis is not available.
    It stores all data in a Python dictionary with TTL tracking.

    Thread-Safety:
        All operations are protected by a threading.Lock to ensure
        thread-safe access in multi-threaded environments (like Streamlit).

    Storage Format:
        {
            "key": {
                "value": <serialized_value>,
                "expires_at": <unix_timestamp>
            }
        }

    Limitations:
        - Cache is NOT shared between processes/workers
        - Cache is lost on application restart
        - Memory usage is bounded only by available RAM

    Use Case:
        - Development environment
        - Single-worker deployments
        - Testing
    """

    def __init__(self):
        """Initialize the in-memory cache with thread lock."""
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the memory cache.

        Checks expiration and removes expired entries automatically.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        with self._lock:
            entry = self._store.get(key)

            if entry is None:
                return None

            # Check if expired
            if entry["expires_at"] < time.time():
                # Remove expired entry
                del self._store[key]
                return None

            # Deserialize and return
            return _deserialize(entry["value"])

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Store a value in the memory cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        with self._lock:
            self._store[key] = {
                "value": _serialize(value),
                "expires_at": time.time() + ttl
            }

    def delete(self, key: str) -> None:
        """
        Remove a key from the memory cache.

        Args:
            key: Cache key to delete
        """
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """
        Clear all entries from the memory cache.
        """
        with self._lock:
            self._store.clear()

    def exists(self, key: str) -> bool:
        """
        Check if a key exists and is not expired.

        Args:
            key: Cache key

        Returns:
            True if key exists and is valid, False otherwise
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False

            # Check expiration
            if entry["expires_at"] < time.time():
                del self._store[key]
                return False

            return True

    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.

        Args:
            key: Cache key

        Returns:
            Remaining seconds, or None if key doesn't exist
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            remaining = entry["expires_at"] - time.time()
            if remaining <= 0:
                del self._store[key]
                return None

            return int(remaining)

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        This is a maintenance method not required by the abstract interface,
        but useful for memory management in long-running applications.

        Returns:
            Number of entries removed
        """
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, v in self._store.items()
                if v["expires_at"] < now
            ]
            for key in expired_keys:
                del self._store[key]
            return len(expired_keys)

    def size(self) -> int:
        """
        Get the number of entries in the cache (including expired).

        Returns:
            Number of cached entries
        """
        with self._lock:
            return len(self._store)


# =============================================================================
# REDIS CACHE IMPLEMENTATION
# =============================================================================

class RedisCache(CacheBackend):
    """
    Redis-based cache implementation for distributed caching.

    This backend uses Redis as a shared cache store, allowing multiple
    workers/processes to share the same cache. This is essential for
    production deployments with multiple Streamlit workers.

    Features:
        - Shared across all workers/containers
        - Automatic expiration via Redis TTL
        - JSON serialization (secure, no pickle)
        - Key prefixing to avoid collisions

    Requirements:
        - Redis server running and accessible
        - redis Python package installed

    Configuration:
        Set REDIS_URL environment variable:
        - Default: redis://localhost:6379/0
        - Docker: redis://redis:6379/0
        - Production: redis://:password@host:6379/db

    Key Format:
        All keys are prefixed with "etdcs:" to avoid collisions.
        Example: etdcs:stats:Morjan:HVAC:All
    """

    def __init__(self, url: str = REDIS_URL):
        """
        Initialize the Redis cache connection.

        Args:
            url: Redis connection URL

        Raises:
            redis.ConnectionError: If Redis is not available
        """
        if not _REDIS_AVAILABLE:
            raise ImportError("Redis package is not installed. Install with: pip install redis")

        self._client = redis.from_url(url, decode_responses=True)
        self._prefix = KEY_PREFIX

        # Test connection
        try:
            self._client.ping()
        except redis.ConnectionError as e:
            raise redis.ConnectionError(f"Cannot connect to Redis at {url}: {e}")

    def _full_key(self, key: str) -> str:
        """
        Build the full Redis key with prefix.

        Args:
            key: Application-level key

        Returns:
            Full key with prefix
        """
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from Redis.

        Args:
            key: Cache key (without prefix)

        Returns:
            Cached value if found, None otherwise
        """
        full_key = self._full_key(key)
        data = self._client.get(full_key)

        if data is None:
            return None

        return _deserialize(data)

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Store a value in Redis with TTL.

        Args:
            key: Cache key (without prefix)
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        full_key = self._full_key(key)
        serialized = _serialize(value)
        self._client.setex(full_key, ttl, serialized)

    def delete(self, key: str) -> None:
        """
        Remove a key from Redis.

        Args:
            key: Cache key (without prefix)
        """
        full_key = self._full_key(key)
        self._client.delete(full_key)

    def clear(self) -> None:
        """
        Clear all ETDCS cache entries from Redis.

        Only clears keys with the etdcs: prefix to avoid affecting
        other applications using the same Redis instance.
        """
        # Find all keys with our prefix
        pattern = f"{self._prefix}*"
        keys = self._client.keys(pattern)

        if keys:
            self._client.delete(*keys)

    def exists(self, key: str) -> bool:
        """
        Check if a key exists in Redis.

        Args:
            key: Cache key (without prefix)

        Returns:
            True if key exists, False otherwise
        """
        full_key = self._full_key(key)
        return bool(self._client.exists(full_key))

    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.

        Args:
            key: Cache key (without prefix)

        Returns:
            Remaining seconds, or None if key doesn't exist
        """
        full_key = self._full_key(key)
        ttl = self._client.ttl(full_key)

        # Redis returns -2 if key doesn't exist, -1 if no expiry
        if ttl == -2:
            return None
        if ttl == -1:
            return -1  # No expiry set

        return ttl

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Redis connection statistics.

        This is a Redis-specific method not in the abstract interface.

        Returns:
            Dictionary with Redis info
        """
        info = self._client.info()
        return {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            "total_keys": len(self._client.keys(f"{self._prefix}*"))
        }


# =============================================================================
# CACHE FACTORY / AUTO-DETECTION
# =============================================================================

def _create_cache_backend() -> CacheBackend:
    """
    Create the appropriate cache backend based on availability.

    Priority:
        1. RedisCache if redis is installed and server is available
        2. MemoryCache as fallback

    Returns:
        CacheBackend instance (RedisCache or MemoryCache)
    """
    # Try Redis first
    if _REDIS_AVAILABLE:
        try:
            backend = RedisCache(REDIS_URL)
            print(f"✓ Cache backend: Redis ({REDIS_URL})")
            return backend
        except Exception as e:
            print(f"⚠ Redis not available, falling back to memory cache: {e}")

    # Fallback to memory cache
    print("✓ Cache backend: In-Memory (single-worker mode)")
    return MemoryCache()


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================
# This is the primary interface for the application.
# The singleton is created at import time.

cache: CacheBackend = _create_cache_backend()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_cache() -> CacheBackend:
    """
    Get the current cache backend instance.

    Returns:
        Active CacheBackend instance
    """
    return cache


def is_redis() -> bool:
    """
    Check if Redis is being used as the cache backend.

    Returns:
        True if using RedisCache, False if using MemoryCache
    """
    return isinstance(cache, RedisCache)


def get_cache_type() -> str:
    """
    Get a string describing the current cache backend type.

    Returns:
        "redis" or "memory"
    """
    return "redis" if is_redis() else "memory"


# =============================================================================
# CACHE INVALIDATION HELPERS
# =============================================================================

def invalidate_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern.

    This is useful for clearing all cache entries related to a specific
    project or data type.

    Args:
        pattern: Key pattern (e.g., "stats:*", "tasks:Morjan:*")

    Returns:
        Number of keys invalidated
    """
    count = 0

    if isinstance(cache, RedisCache):
        # Redis supports pattern matching
        full_pattern = f"{KEY_PREFIX}{pattern}"
        keys = cache._client.keys(full_pattern)
        if keys:
            cache._client.delete(*keys)
            count = len(keys)

    elif isinstance(cache, MemoryCache):
        # Memory cache: iterate and match
        with cache._lock:
            keys_to_delete = [
                k for k in cache._store.keys()
                if k.startswith(pattern.split("*")[0])
            ]
            for key in keys_to_delete:
                del cache._store[key]
            count = len(keys_to_delete)

    return count


def invalidate_project(project_name: str) -> int:
    """
    Invalidate all cache entries for a specific project.

    Args:
        project_name: Project reference/name

    Returns:
        Number of keys invalidated
    """
    return invalidate_pattern(f"*:{project_name}:*")


# =============================================================================
# DEBUGGING / TESTING UTILITIES
# =============================================================================

def debug_cache_state() -> Dict[str, Any]:
    """
    Get debug information about the cache state.

    Returns:
        Dictionary with cache statistics and sample keys
    """
    state = {
        "backend_type": get_cache_type(),
        "redis_available": _REDIS_AVAILABLE,
        "redis_url": REDIS_URL if _REDIS_AVAILABLE else None,
    }

    if isinstance(cache, MemoryCache):
        state["memory_cache"] = {
            "size": cache.size(),
            "keys": list(cache._store.keys())[:20]  # First 20 keys
        }

    elif isinstance(cache, RedisCache):
        try:
            state["redis_stats"] = cache.get_stats()
        except Exception as e:
            state["redis_error"] = str(e)

    return state
