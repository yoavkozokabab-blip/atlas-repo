from cache.redis_client import RedisClient

cache = RedisClient()

def get_cached(key):
    return cache.get(key)
