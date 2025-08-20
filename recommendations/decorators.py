from functools import wraps
from django.core.cache import cache
import logging
import time

logger = logging.getLogger(__name__)

def cache_with_build_lock(lock_key_prefix, cache_key_constant, builder_method_name, lock_timeout=600):
    """
    A decorator to prevent cache stampedes when building expensive cache items.

    It wraps a getter function. If the item is not in the cache (or if
    `force_refresh` is True), it attempts to acquire a lock. If successful,
    it calls the specified builder method. If locked, it waits and retries.

    Args:
        lock_key_prefix (str): A unique prefix for the lock key to avoid
                               collisions with other locks.
        cache_key_constant (str): The actual key where the final resource is stored.
        builder_method_name (str): The name of the method on the instance (`self`)
                                   that builds and caches the resource.
        lock_timeout (int): Timeout for the lock in seconds.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, force_refresh=False):
            if not force_refresh:
                cached_value = cache.get(cache_key_constant)
                if cached_value is not None:
                    logger.debug(f"Serving '{cache_key_constant}' from cache.")
                    return cached_value

            lock_key = f"{lock_key_prefix}:{cache_key_constant}"

            # Try to acquire the lock
            if cache.add(lock_key, 'building', timeout=lock_timeout):
                logger.info(f"Acquired lock '{lock_key}' to build resource.")
                try:
                    # Call the builder method (e.g., 'rebuild_user_similarity_cache')
                    builder = getattr(self, builder_method_name)
                    new_value = builder()
                    return new_value
                finally:
                    # Always release the lock
                    cache.delete(lock_key)
                    logger.info(f"Released lock '{lock_key}'.")
            else:
                # If lock is not acquired, wait and retry the entire get operation
                logger.info(f"Cache build for '{cache_key_constant}' is locked. Waiting...")
                time.sleep(5)
                return wrapper(self, force_refresh=False)
        return wrapper
    return decorator
