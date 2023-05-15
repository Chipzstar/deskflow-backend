from datetime import timedelta
import os
import redis

HOST = os.environ.get('REDIS_HOST', 'localhost')
PORT = int(os.environ.get('REDIS_PORT', 6379))
DB = int(os.environ.get('REDIS_DB', 0))
USERNAME = os.environ.get('REDIS_USERNAME', None)
PASSWORD = os.environ.get('REDIS_PASSWORD', None)
SOCKET_TIMEOUT = os.environ.get('REDIS_SOCKET_TIMEOUT', None)


class Redis(object):
    def __init__(self, host=HOST, port=PORT, db=DB, username=USERNAME, password=PASSWORD, socket_timeout=SOCKET_TIMEOUT):
        # Set up Redis client
        pool = redis.ConnectionPool(host=host, port=port, db=0)
        self.__redis = redis.Redis(connection_pool=pool)

    def add_to_cache(self, key, value, ttl):
        self.__redis.setex(key, ttl, value=value)

    def get_ttl(self, key):
        return self.__redis.ttl(key)

    def get_value(self, key):
        return self.__redis.get(key)
