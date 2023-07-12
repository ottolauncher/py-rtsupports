import datetime
import json
from typing import Optional, List, Union, Iterable

import strawberry
from rethinkdb import r
from rethinkdb.asyncio_net.net_asyncio import AsyncioCursor
from strawberry.field_extensions import InputMutationExtension
from strawberry.scalars import JSON
from strawberry.types import Info
from typing_extensions import AsyncGenerator, TYPE_CHECKING, Annotated

from db import get_connection, messageTbl, userTbl
from utils.wrapper import json_serial

if TYPE_CHECKING:
    from .channels import ChannelType
    from .users import UserType


@strawberry.type
class MessageChangesType:
    changes: JSON


@strawberry.type
class MessageType:
    created_at: Optional[datetime.datetime]
    user_id: Optional[strawberry.ID] = None
    channel_id: Optional[strawberry.ID] = None
    text: Optional[str] = None
    id: Optional[str] = None

    @strawberry.field
    async def channels(self, info: Info) -> List[Annotated['ChannelType', strawberry.lazy('.channels')]]:
        return await info.context['channel_loader'].load(self.channel_id)

    @strawberry.field
    async def users(self, info: Info) -> List[Annotated['UserType', strawberry.lazy('.users')]]:
        return await info.context['user_loader'].load(self.user_id)


async def make_default_message(cur) -> MessageType:
    return MessageType(
        id=cur.get('id'),
        text=cur.get('text'),
        created_at=cur.get('created_at'),
        user_id=cur.get('user_id'),
        channel_id=cur.get('channel_id'),
    )


async def make_message(cur) -> MessageType:
    if isinstance(cur, AsyncioCursor):
        try:
            while (await cur.fetch_next()):
                message = await cur.next()
                return await make_message(message)
        finally:
            cur.close()
    else:
        return MessageType(
            id=cur.get('id'),
            text=cur.get('text'),
            created_at=cur.get('created_at'),
            user_id=cur.get('user_id'),
            channel_id=cur.get('channel_id'),
        )


async def make_messages(cur) -> List[MessageType]:
    messages: List[MessageType] = []
    if isinstance(cur, AsyncioCursor):
        try:
            while (await cur.fetch_next()):
                item = await cur.next()
                messages.append(await make_message(item))
        finally:
            cur.close()
    return messages


async def load_messages(keys: List[strawberry.ID]) -> List[Union[MessageType, ValueError]]:
    conn = await get_connection()
    res = await r.table(messageTbl).filter(
        lambda msg: r.expr(keys).contains(msg('id'))
    ).limit(len(keys)).run(conn)
    messages: List[MessageType] = []
    try:
        while (await res.fetch_next()):
            item = await res.next()
            messages.append(await make_default_message(item))
    finally:
        res.close()
    return messages


async def load_messages_by_channel(keys: List[strawberry.ID]) -> Iterable[List[MessageType]]:
    conn = await get_connection()
    res = await r.table(messageTbl).filter(
        lambda doc: r.expr(keys).contains(doc['channel_id'])
    ).limit(len(keys)).run(conn)
    try:
        messages = await make_messages(res)
        groups = {k: [] for k in keys}
        for m in messages:
            groups[m.channel_id].append(m)
        return groups.values()
    finally:
        res.close()


async def load_messages_by_user(keys: List[strawberry.ID]) -> Iterable[List[MessageType]]:
    conn = await get_connection()
    res = await r.table(messageTbl).filter(
        lambda doc: r.expr(keys).contains(doc['user_id'])
    ).limit(len(keys)).run(conn)
    try:
        messages = await make_messages(res)
        groups = {k: [] for k in keys}
        for m in messages:
            groups[m.user_id].append(m)
        return groups.values()

    finally:
        res.close()


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
        return await make_message(res)

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
        res = await r.table(messageTbl).get(filter).update(message, return_changes=True).run(conn)

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
    async def get_message(self, info: Info, filter: JSON) -> MessageType:
        conn = await get_connection()
        res = await r.table(messageTbl).filter(filter).limit(1).run(conn)
        try:
            message = await make_message(res)
            return message
        finally:
            res.close()

    @strawberry.field
    async def all_messages(self, info: Info, filter: Optional[JSON] = None, page: Optional[int] = None,
                           limit: Optional[int] = None) -> List[MessageType]:
        conn = await get_connection()
        if filter is None:
            filter = {}
        if page is None:
            page = 0
        if limit is None:
            limit = 12
        res = await r.table(messageTbl).filter(filter).limit(limit).skip(page).run(conn)
        try:
            messages = await make_messages(res)
            return messages
        finally:
            res.close()


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
            await conn.close()
            print("Connection lost cursor closed")
        finally:
            feeds.close()
