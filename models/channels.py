import datetime
import json
from typing import Optional, List, Iterable

import strawberry
from rethinkdb import r
from rethinkdb.asyncio_net.net_asyncio import AsyncioCursor
from strawberry.field_extensions import InputMutationExtension
from strawberry.scalars import JSON
from strawberry.types import Info
from typing_extensions import AsyncGenerator, Annotated, TYPE_CHECKING

from db import get_connection, channelTbl
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
    id: Optional[str] = None

    @strawberry.field
    async def messages(self, info: Info) -> List[Annotated['MessageType', strawberry.lazy('.messages')]]:
        return await info.context['channel_messages_loader'].load(self.id)


async def make_channel(cur) -> ChannelType:
    if isinstance(cur, AsyncioCursor):
        try:
            while (await cur.fetch_next()):
                channel = await cur.next()
                return await make_channel(channel)
        finally:
            cur.close()
    else:
        return ChannelType(
            id=cur.get('id'),
            name=cur.get('name'),
            created_at=cur.get('created_at')
        )


async def make_channels(res) -> List[ChannelType]:
    channels: List[ChannelType] = []
    if isinstance(res, AsyncioCursor):
        try:
            while (await res.fetch_next()):
                channel = await res.next()
                channels.append(await make_channel(channel))
        finally:
            res.close()
    if isinstance(res, list):
        channels = [await make_channel(c) for c in res]
    return channels


async def load_channels(keys: List[strawberry.ID]) -> Iterable[List[ChannelType]]:
    conn = await get_connection()
    cur = await r.table(channelTbl).get_all(r.args(keys)).run(conn)
    try:
        users = await make_channels(cur)
        groups = {k: [] for k in keys}
        for u in users:
            groups[u.id].append(u)
        return groups.values()
    finally:
        cur.close()


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
                    return await make_channel(item)
                break

        res = await r.table(channelTbl).insert(channel, return_changes=True).run(conn)
        change = res.get('changes')[0]['new_val']
        return await make_channel(change)

    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def add_channel(self, name: str) -> ChannelType:
        conn = await get_connection()
        channel = {
            'name': name,
            'created_at': r.now()
        }
        res = await r.table(channelTbl).insert(channel, return_changes=True).run(conn)
        change = res.get('changes')[0]['new_val']
        return await make_channel(change)

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
            return await make_channel(new_val)
        return await make_channel(res)

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
        res = await r.table(channelTbl).filter(filter).run(conn)
        try:
            return await make_channel(res)
        finally:
            res.close()


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
        try:
            channels = await make_channels(res)
            return channels
        finally:
            res.close()


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
