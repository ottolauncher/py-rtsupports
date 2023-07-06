import datetime
import json
from typing import Optional, List, Union
import strawberry
from rethinkdb import r
from rethinkdb.asyncio_net.net_asyncio import AsyncioCursor
from strawberry.field_extensions import InputMutationExtension
from strawberry.scalars import JSON
from strawberry.types import Info
from typing_extensions import AsyncGenerator

from db import get_connection, userTbl, messageTbl
from utils.wrapper import json_serial


@strawberry.type
class UserChangeType:
    changes: JSON


@strawberry.type
class UserType:
    username: str
    created_at: Optional[datetime.datetime]
    id: Optional[str] = None


def make_user(cur) -> UserType:
    return UserType(
        id=cur.get('id'),
        username=cur.get('username'),
        created_at=cur.get('created_at')
    )


async def load_users(keys: List[strawberry.ID]) -> List[Union[UserType, ValueError]]:
    async def lookup(key: strawberry.ID) -> Union[UserType, ValueError]:
        conn = await get_connection()
        res = await r.table(userTbl).get(key).run(conn)
        if res.get('id', None) is not None:
            return make_user(res)
        return ValueError("user does not exists")

    return [await lookup(key) for key in keys]


async def load_users_by_message(keys: List[strawberry.ID]) -> List[Union[UserType, ValueError]]:
    conn = await get_connection()
    res = await r.table(messageTbl).filter(
        lambda doc: r.expr(keys).contains(doc['user_id'])
    ).run(conn)
    users: List[UserType] = []
    while (await res.fetch_next()):
        usr = await res.next()
        users.append(make_user(usr))
    return users

@strawberry.type
class UserMutation:
    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def get_or_create_user(self, username: str) -> UserType:
        conn = await get_connection()
        user = {
            'username': username
        }
        cur = await r.table(userTbl).filter(user).limit(1).run(conn)
        if isinstance(cur, AsyncioCursor):
            while (await cur.fetch_next()):
                item = await cur.next()
                if item.get('id', None) is not None:
                    return make_user(item)
                break

        return await self.add_user(username)

    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def add_user(self, username: str) -> UserType:
        conn = await get_connection()
        user = {
            'username': username,
            'created_at': r.now()
        }
        res = await r.table(userTbl).insert(user, return_changes=True).run(conn)
        change = res.get('changes')[0]['new_val']
        return make_user(change)

    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def update_channel(self, pk: strawberry.ID, username: str) -> UserType:
        query = {
            'id': pk,
        }
        update = {
            'username': username
        }
        conn = await get_connection()
        res = await r.table(userTbl).filter(query).update(update, return_changes=True).run(conn)
        if res.get('unchanged') == 0:
            new_val = res.get('changes')[0]['new_val']
            return make_user(new_val)
        return UserType()

    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def delete_channel(self, pk: strawberry.ID) -> bool:
        conn = await get_connection()
        res = await r.table(userTbl).get({'id': pk}).delete().run(conn)
        if res.get('deleted') == 1:
            return True
        return False


async def make_users(res) -> List[UserType]:
    users: List[UserType] = []
    while (await res.fetch_next()):
        user = await res.next()
        users.append(make_user(user))
    return users


@strawberry.type
class UserQuery:
    @strawberry.field
    async def get_user(self, info: Info, id: strawberry.ID) -> UserType:
        return await info.context["user_loader"].load(id)

    @strawberry.field
    async def all_users(self, filter: Optional[JSON] = None, page: Optional[int] = None,
                        limit: Optional[int] = None) -> List[UserType]:
        conn = await get_connection()
        if filter is None:
            filter = {}
        if page is None:
            page = 0
        if limit is None:
            limit = 12
        res = await r.table(userTbl).filter(filter).limit(limit).skip(page).run(conn)
        users = await make_users(res)
        return users


@strawberry.type
class UserSubscription:
    @strawberry.subscription
    async def user_changed(self) -> AsyncGenerator[UserType, None]:
        conn = await get_connection()
        feeds = await r.table(userTbl).changes().run(conn)
        try:
            while (await feeds.fetch_next()):
                item = await feeds.next()
                dumps = json.dumps(item, default=json_serial)
                changes = UserChangeType(changes=dumps)
                yield changes
        except GeneratorExit:
            await feeds.close()
            print("Connection lost cursor closed")
