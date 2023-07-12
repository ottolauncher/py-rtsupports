from io import BytesIO

import msgpack
from strawberry.dataloader import AbstractCache
from typing import Any, Union


from db.redis import redis_cli

redis_cli.ping()

CHUNK_SIZE = 5000
content = BytesIO()


def clear_ns(ns):
    """
    Clears a namespace
    :param ns: str, namespace i.e. your:prefix
    :return: int, cleared keys
    """
    cursor = '0'
    ns_keys = ns + '*'
    while cursor != 0:
        cursor, keys = redis_cli.scan(cursor=cursor, match=ns_keys, count=CHUNK_SIZE)
        if keys:
            redis_cli.delete(*keys)

    return True


class UserCache(AbstractCache):
    ns = 'rtsupports:users'

    def __init__(self):
        self.redis_cli = redis_cli

    def get(self, key: Any) -> Union[Any, None]:
        if self.redis_cli.exists(f'{self.ns}:{key}'):
            value = self.redis_cli.hgetall(f'{self.ns}:{key}')
            return msgpack.unpackb(value, raw=False)
        return None

    async def set(self, key: Any, value: Any) -> None:
        res = await value
        msg = msgpack.packb(res, use_bin_type=True)
        self.redis_cli.hset(f'{self.ns}:{key}', msg)
        return None

    def delete(self, key: Any) -> None:
        self.redis_cli.delete(f'{self.ns}:{key}')

    def clear(self) -> None:
        clear_ns(self.ns)

class ChannelCache(AbstractCache):
    ns = 'rtsupports:channels'

    def __init__(self):
        self.redis_cli = redis_cli

    def get(self, key: Any) -> Union[Any, None]:
        byte = self.redis_cli.get(f'{self.ns}:{key}')
        return msgpack.unpackb(byte, raw=False)

    async def set(self, key: Any, value: Any) -> None:
        res = await value
        byte = msgpack.packb(res, use_bin_type=True)
        self.redis_cli.hset(f'{self.ns}:{key}', byte)
        return None

    def delete(self, key: Any) -> None:
        self.redis_cli.delete(f'{self.ns}:{key}')

    def clear(self) -> None:
        clear_ns(self.ns)
