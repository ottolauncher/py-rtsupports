import datetime
import json
from asyncio import run
from typing import Optional, List
import strawberry
from rethinkdb import r
from rethinkdb.asyncio_net.net_asyncio import AsyncioCursor
from strawberry.field_extensions import InputMutationExtension
from strawberry.scalars import JSON
from strawberry.types import Info
from typing_extensions import AsyncGenerator, Annotated, TYPE_CHECKING

from db import get_connection, messageTbl, userTbl, channelTbl
from models.channels import ChannelType, make_channel
from models.users import UserType, make_user
from utils.wrapper import json_serial


if TYPE_CHECKING:
    from .channels import ChannelType


@strawberry.type
class MessageChangesType:
    changes: JSON


@strawberry.type
class MessageType:
    text: str
    created_at: Optional[datetime.datetime]
    user_id: Optional[strawberry.ID] = None
    channel_id: Optional[strawberry.ID] = None
    channels: Optional[List[ChannelType]] = None
    users: Optional[List[UserType]] = None
    id: Optional[str] = None

    @strawberry.field
    async def channels(self, info: Info, keys: List[strawberry.ID]) -> List[Annotated["ChannelType", strawberry.lazy(".channels")]]:
        return await info.context['channels_by_message'].load(keys)


async def make_message(cur) -> MessageType:
    if isinstance(cur, AsyncioCursor):
        while (await cur.fetch_next()):
            message = await cur.next()
            return await make_message(message)
    else:
        users = [make_user(u) for u in cur.get('users')]
        channels = [make_channel(c) for c in cur.get('channels')]
        return MessageType(
            id=cur.get('id'),
            text=cur.get('text'),
            created_at=cur.get('created_at'),
            user_id=cur.get('user_id'),
            channel_id=cur.get('channel_id'),
            channels=channels,
            users=users
        )


async def load_messages_by_channel(keys: List[strawberry.ID]) -> List[MessageType]:
    conn = await get_connection()
    res = await r.table(messageTbl).filter(
        lambda doc: r.expr(keys).contains(doc['channel_id'])
    ).run(conn)
    messages: List[MessageType] = []
    while (await res.fetch_next()):
        msg = await res.next()
        messages.append(await make_message(msg))
    return messages


async def prefetch_related(msg):
    conn = await get_connection()
    if isinstance(msg, str):
        res = await r.table(messageTbl).get(msg).merge(lambda message: {
            "users": r.table(userTbl).get_all(message['user_id']).coerce_to('ARRAY'),
            "channels": r.table(channelTbl).get_all(message['channel_id']).coerce_to('ARRAY')
        }).run(conn)

        return res


def sync_prefetch_related(msg):
    return {
        "users": r.table(userTbl).get_all(msg['user_id']).coerce_to('ARRAY'),
        "channels": r.table(channelTbl).get_all(msg['channel_id']).coerce_to('ARRAY')
    }


@strawberry.type
class MessageMutation:
    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def add_message(self, user_id: strawberry.ID, channel_id: strawberry.ID, text: str) -> MessageType:
        conn = await get_connection()
        message = {
            'user_id': user_id,
            'channel_id': channel_id,
            'text': text,
            'created_at': r.now(),
        }
        res = await r.table(messageTbl).insert(message).run(conn)
        item = await prefetch_related(res['generated_keys'][0])
        return MessageType(
            users=item.get('users'),
            channels=item.get('channels'),
            user_id=item.get('user_id'),
            channel_id=item.get('channel_id'),
            id=item.get('id'),
            created_at=item.get('created_at'),
            text=item.get('text')
        )

    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def update_message(self, id: strawberry.ID, user_id: strawberry.ID, channel_id: strawberry.ID,
                             text: str) -> MessageType:
        conn = await get_connection()
        message = {
            'user_id': user_id,
            'channel_id': channel_id,
            'text': text
        }
        filter = {'id': id}
        res = await r.table(messageTbl).get(filter).update(message, return_changes=True).merge(
            lambda msg: run(prefetch_related(msg))
        ).run(conn)

        if res.get('unchanged') == 0:
            new_val = res.get('changes')[0]['new_val']
            return await make_message(new_val)
        return MessageType()

    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def delete_mutation(self, id: strawberry.ID) -> bool:
        conn = await get_connection()
        filter = {'id': id}
        res = await r.table(messageTbl).get(filter).delete().run(conn)

        if res.get('deleted') == 1:
            return True
        return False


@strawberry.type
class MessageQuery:
    @strawberry.field
    async def get_message(self, filter: JSON) -> MessageType:
        conn = await get_connection()
        res = await r.table(messageTbl).filter(filter).merge(
            lambda msg: sync_prefetch_related(msg)
        ).run(conn)
        return await make_message(res)

    @strawberry.field
    async def all_messages(self, info: Info, filter: Optional[JSON] = None, page: Optional[int] = None,
                           limit: Optional[int] = None) -> List[MessageType]:
        messages: List[MessageType] = []
        conn = await get_connection()
        if filter is None:
            filter = {}
        if page is None:
            page = 0
        if limit is None:
            limit = 12
        # res = await r.table(messageTbl).filter(filter).limit(limit).skip(page).merge(
        #     lambda msg: sync_prefetch_related(msg)
        # ).run(conn)
        res = await r.table(messageTbl).filter(filter).limit(limit).skip(page).run(conn)
        while (await res.fetch_next()):
            item = await res.next()
            msg = MessageType(
                id=item.get('id'),
                text=item.get('text'),
                created_at=item.get('created_at'),
                user_id=item.get('user_id'),
                channel_id=item.get('channel_id'),
            )
            messages.append(msg)
        return messages


@strawberry.type
class MessageSubscription:
    @strawberry.subscription
    async def messages_changes_by_channel_id(self, info, channel_id: strawberry.ID) -> AsyncGenerator[
        MessageChangesType, None]:
        conn = await get_connection()
        feeds = await r.table(messageTbl).filter({'channel_id': channel_id}).changes(include_initial=True).run(conn)
        try:
            while (await feeds.fetch_next()):
                item = await feeds.next()
                dumps = json.dumps(item, default=json_serial)
                changes = MessageChangesType(changes=dumps)
                yield changes
        except GeneratorExit:
            await feeds.close()
            print("Connection lost cursor closed")
