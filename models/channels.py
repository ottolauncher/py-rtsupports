import datetime
import json
from typing import Optional, List, Union
import strawberry
from rethinkdb import r
from rethinkdb.asyncio_net.net_asyncio import AsyncioCursor
from strawberry.field_extensions import InputMutationExtension
from strawberry.scalars import JSON
from typing_extensions import AsyncGenerator, Annotated, TYPE_CHECKING

from db import get_connection, channelTbl, messageTbl
from utils.wrapper import json_serial

if TYPE_CHECKING:
    from .messages import MessageType


@strawberry.type
class ChannelChangeType:
    changes: JSON


@strawberry.type
class ChannelType:
    name: str
    created_at: Optional[datetime.datetime]
    messages: Optional[Annotated["MessageType", strawberry.lazy(".messages")]] = None
    id: Optional[str] = None


def make_channel(cur) -> ChannelType:
    if cur is not None:
        return ChannelType(
            id=cur.get('id'),
            name=cur.get('name'),
            created_at=cur.get('created_at')
        )


async def make_channels(res) -> List[ChannelType]:
    channels: List[ChannelType] = []
    while (await res.fetch_next()):
        channel = await res.next()
        channels.append(make_channel(channel))
    return channels


async def load_channels(keys: List[strawberry.ID]) -> List[Union[ChannelType, ValueError]]:
    async def lookup(key: strawberry.ID) -> Union[ChannelType, ValueError]:
        conn = await get_connection()
        res = await r.table(channelTbl).get(key).run(conn)
        if res.get('id', None) is not None:
            return make_channel(res)
        return ValueError("channel does not exists")

    return [await lookup(key) for key in keys]


async def load_channels_by_message(keys: List[strawberry.ID]) -> List[Union[ChannelType, ValueError]]:
    conn = await get_connection()
    res = await r.table(channelTbl).filter(
        lambda chan: r.expr(keys).contains(chan['id'])).merge(lambda chan: {
        "messages": r.table(messageTbl).filter({'channel_id': chan['id']})
    }).run(conn)
    channels = await make_channels(res)
    return channels


@strawberry.type
class ChannelMutation:
    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def get_or_create_channel(self, name: str) -> ChannelType:
        conn = await get_connection()
        channel = {
            'name': name
        }
        cur = await r.table(channelTbl).filter(channel).limit(1).run(conn)
        if isinstance(cur, AsyncioCursor):
            while (await cur.fetch_next()):
                item = await cur.next()
                if item.get('id', None) is not None:
                    return make_channel(item)
                break

        res = await r.table(channelTbl).insert(channel, return_changes=True).run(conn)
        change = res.get('changes')[0]['new_val']
        return make_channel(change)

    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def add_channel(self, name: str) -> ChannelType:
        conn = await get_connection()
        channel = {
            'name': name,
            'created_at': r.now()
        }
        res = await r.table(channelTbl).insert(channel, return_changes=True).run(conn)
        change = res.get('changes')[0]['new_val']
        return make_channel(change)

    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def update_channel(self, pk: strawberry.ID, name: str) -> ChannelType:
        query = {
            'id': pk,
        }
        update = {
            'name': name
        }
        conn = await get_connection()
        res = await r.table(channelTbl).filter(query).update(update, return_changes=True).run(conn)
        if res.get('unchanged') == 0:
            new_val = res.get('changes')[0]['new_val']
            return make_channel(new_val)
        return ChannelType()

    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def delete_channel(self, pk: strawberry.ID) -> bool:
        conn = await get_connection()
        res = await r.table(channelTbl).get({'id': pk}).delete().run(conn)
        if res.get('deleted') == 1:
            return True
        return False


@strawberry.type
class ChannelQuery:
    @strawberry.field
    async def get_channel(self, filter: JSON) -> ChannelType:
        conn = await get_connection()
        res = await r.table(channelTbl).get(filter).run(conn)
        return make_channel(res)

    @strawberry.field
    async def all_channels(self, filter: Optional[JSON] = None, page: Optional[int] = None,
                           limit: Optional[int] = None) -> List[ChannelType]:
        conn = await get_connection()

        if filter is None:
            filter = {}
        if page is None:
            page = 0
        if limit is None:
            limit = 12
        res = await r.table(channelTbl).filter(filter).limit(limit).skip(page).run(conn)
        channels = await make_channels(res)
        return channels


@strawberry.type
class ChannelSubscription:
    @strawberry.subscription
    async def channel_changed(self) -> AsyncGenerator[ChannelChangeType, None]:
        conn = await get_connection()
        feeds = await r.table(channelTbl).changes().run(conn)
        try:
            while (await feeds.fetch_next()):
                item = await feeds.next()
                dumps = json.dumps(item, default=json_serial)
                changes = ChannelChangeType(changes=dumps)
                yield changes
        except GeneratorExit:
            await feeds.close()
            print("Connection lost cursor closed")
