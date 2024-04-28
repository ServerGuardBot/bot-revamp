import config
import redis

valkey = redis.Redis(host=config.VALKEY_IP, port=config.VALKEY_PORT, db=0)