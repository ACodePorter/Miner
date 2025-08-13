from typing import Optional

from redis import Redis

from ._env import is_prod

_reais_client: Optional[Redis] = None


def get_redis_client(host: str = 'localhost', port: int = 6379, db: int = 0) -> Redis:
    global _reais_client
    if _reais_client is None:
        if is_prod():
            host = 'miner-redis'
        try:
            _reais_client = Redis(host=host, port=port, db=db,
                                  decode_responses=True,
                                  health_check_interval=60,
                                  socket_keepalive=True, socket_connect_timeout=30,
                                  retry_on_timeout=True)
        except Exception as e:
            raise Exception(f"Failed to connect to Redis: {e}")
    return _reais_client
