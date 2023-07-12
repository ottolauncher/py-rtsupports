# py-rtsupports
The application has been implemented by following the Udemy course  by  [Build Realtime Apps](https://www.udemy.com/course/realtime-apps-with-reactjs-golang-rethinkdb/) @knowthen
but this using [Strawberry-GraphQL](https://strawberry.rocks/), [RethinkDB](https://rethinkdb.com/) and [Starlette](https://www.starlette.io/)

# Why
As a developer we need to keep sharp buy learning new(old) stuff here and there, by covering almost almost topics like suscriptions on GraphQL
there a plenty tutorial on how to have a GraphQL app (server side at list up and running) but when you try to lean subscriptions and even dataloader
supports it can be a little bit frustrating.
So here we have it a pretty good compilation of what you have always needs.
Happy Coding

# Organization
I have borrowed some project convention from one of my top [Python](https://python.org) framework [Django](https://www.djangoproject.com/) that I use since the version 1.2

## Getting Started
[Strawberry-GraphQL](https://strawberry.rocks/) is pretty awesome with a lot a major framework integration and ideal for big project.

Make it at your ease but the only requirement is Python <= 3.8 and Python > 3.6, we will use [Typing](https://docs.python.org/3/library/typing.html)  and [Typing-Extensions](https://typing-extensions.readthedocs.io/en/latest/) and also because of [RethinkDB](https://rethinkdb.com/) that does not work well with Python>=3.10 some asyncio errors have been encountered so just tick on that for now. After you can add the dependecies from requirements.txt.
According to the course we will need three models User, Channel and Message. The first approach of creating that like 
[Strawberry-Schema](https://strawberry.rocks/docs/types/schema)
```
# models/channels.py
############################################################
# ...

@strawberry.type
class ChannelType:
    name: str
    created_at: Optional[datetime.datetime]
    id: Optional[str] = None

# models/users.py
############################################################

# ....
@strawberry.type
class UserType:
    username: str
    created_at: Optional[datetime.datetime]
    id: Optional[str] = None

# models/messages.py
############################################################

# ...

@strawberry.type
class MessageType:
    created_at: Optional[datetime.datetime]
    user_id: Optional[strawberry.ID] = None
    channel_id: Optional[strawberry.ID] = None
    text: Optional[str] = None
    id: Optional[str] = None
```

### Connect to [RethinkDB](https://rethinkdb.com/)

```
# db
# We create table name globally 
userTbl = 'users'
channelTbl = 'channels'
messageTbl = 'messages'

# We specify RethinkDB loop_type asyncio | tornado | ... more in docs
r.set_loop_type('asyncio')

# We create and return the db connection instance
async def get_connection():
    return await r.connect(
        db='rtsupports',
        host='localhost'
    )

# A little tips from Golang World
async def init():
    try:
        conn = await get_connection()
        r.table_create(userTbl).run(conn)
        r.table_create(channelTbl).run(conn)
        r.table_create(messageTbl).run(conn)

    except ReqlOpFailedError:
        # handle error here
        pass
```

### Minimum Server
We can use the default [Strawberry-GraphQL](https://strawberry.rocks/) server but as we've programmed to use [Starlette](https://www.starlette.io/)
let shine amongs the stars should we!?
```
# server .py

class MyGraphQL(GraphQL):
    # It will be use in future when we will added Dataloader
    pass


graphql_app = MyGraphQL(schema=schema)

outes = [
    Route("/graphql", graphql_app),
    WebSocketRoute("/graphql", graphql_app),
]

middlewares = [
    Middleware(
        CORSMiddleware, allow_origins=[
            'http://localhost:8000', 'http://localhost:5173', '127.0.0.1',
        ],
        allow_credentials=True,
        allow_headers=['*'],
        allow_methods=['*'],
    )
]
app = Starlette(debug=settings.DEBUG, routes=routes, middleware=middlewares)

async def main():
    run_once(init)
    config = uvicorn.Config("server:app", port=8000, lifespan="auto")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

```
We have add CORSMiddleware early because we will use a separated frontend environement so to stay out of troubles...

### Create  Mutation

```
# models/users.py
# ....

# Some code refactoring to avoid repeating
async def make_user(cur) -> UserType:
    if isinstance(cur, AsyncioCursor):
        try:
            while (await cur.fetch_next()):
                user = await cur.next()
                return await make_user(user)
        finally:
            cur.close()
    return UserType(
        id=cur.get('id'),
        username=cur.get('username'),
        created_at=cur.get('created_at')
    )

def pluck(lst, key) -> List[Any]:
    return [x.get(key) for x in lst]


@strawberry.type
class UserMutation:
     @strawberry.mutation(extensions=[InputMutationExtension()])
     async def add_user(self, username: str) -> UserType:
            conn = await get_connection()
            user = {
                'username': username,
                'created_at': r.now()
            }
            res = await r.table(userTbl).insert(user, return_changes=True).run(conn)
            change = res.get('changes')[0]['new_val']
            return await make_user(change)

    @strawberry.mutation
    async def bulk_channel(self, names: List[str]) -> List[ChannelType]:
        conn = await get_connection()
        channels = [{"name": name} for name in names]
        try:
            cur = await r.table(channelTbl).insert(channels, return_changes=True).run(conn)
            changes = pluck(cur.get('changes'), 'new_val')
            return await make_channels(changes)
        finally:
            conn.close()

```
The code is pretty much self explanatory, we just get RethinkDB connection instance, grab incoming GraphQL input data and perform a simple create operation. In case on Bulk insertion the bulk function deal with that.

### Let take a look of a possible GraphQL Mutation
First we need to run our server 
```
bash
python -m server
```
Then we navigate to the GraphiQL location:
```
http://localhost:8000/graphql
```
Now we can insert our first mutation query
```
mutation BULK_CHANNEL($input: [String!]!) {
  bulkChannel(names: $input) {
    id
    name
  }
}
... variables
{
  "input": [
   "Mango", "Java"
  ]
}
```
Who should reply with something similar to this
```
{
  "data": {
    "bulkChannel": [
      {
        "id": "21b64ae6-ce09-4703-b177-918f7ff5ff02",
        "name": "Mango"
      },
      {
        "id": "4a83daa2-44b2-4b63-a1d1-6a1128f9a691",
        "name": "Java"
      }
    ]
  }
}
```
The same goes for addChannel mutation in troubles refer to [GraphQL Queries & Mutations](https://graphql.org/learn/queries/)
Comming from Django we can also implement a get_or_create method like this:
```
    @strawberry.mutation(extensions=[InputMutationExtension()])
    async def get_or_create_channel(self, name: str) -> ChannelType:
        conn = await get_connection()
        channel = {
            'name': name
        }
        cur = await r.table(channelTbl).filter(channel).limit(1).run(conn)
        if isinstance(cur, AsyncioCursor):
            return await make_channel(cur)
        res = await r.table(channelTbl).insert(channel, return_changes=True).run(conn)
        change = res.get('changes')[0]['new_val']
        return await make_channel(change)
```
Oh yes the [InputMutationExtension](https://strawberry.rocks/docs/general/mutations) It is usually useful to use a pattern of defining a mutation that receives a single input type argument called input.
And why those try...finally block? Oh well to avoid task pending warning on console.

### Create  Query
```
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
```
On GraphiQL
```
query ALL_CHANNEL {
    allChannels{
      id
      name
    }
}
# Or
query ALL_CHANNEL($filter: JSON=null, $page: Int=null, $limit: Int=null) {
    allChannels(filter: $filter, page: $page, limit: $limit){
      id
      name
    }
}
```
### Create Subscriptions
Yes the forgotten part of many tutorials just for You right here
```
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
```
We take avantages on the [RethinkDB](https://rethinkdb.com/) realtimes changes feeds and try to stick with the courses implementations of it but a more pythonista way.

## RelationShip
On the course it seem like we only have one to many like relationship so in this part we will try to deal with.
we can for example use the merge function of [RethinkDB](https://rethinkdb.com/) to make sure that channels and users is always available when someone requested messages but it break the elegant way to do it like GraphQL recommandation. So instead of doing this:
```
# models/messages.py

@strawberry.type
class MessageType:
    text: str
    created_at: Optional[datetime.datetime]
    user_id: Optional[strawberry.ID] = None
    channel_id: Optional[strawberry.ID] = None
    channels: Optional[List[ChannelType]] = None
    users: Optional[List[UserType]] = None
    id: Optional[str] = None

async def prefetch_related(msg):
    conn = await get_connection()
    if isinstance(msg, str):
        res = await r.table(messageTbl).get(msg).merge(lambda message: {
            "users": r.table(userTbl).get_all(message['user_id']).coerce_to('ARRAY'),
            "channels": r.table(channelTbl).get_all(message['channel_id']).coerce_to('ARRAY')
        }).run(conn)

        return res

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
        try:
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
        finally:
            res.close()

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
        res = await r.table(messageTbl).filter(filter).limit(limit).skip(page).run(conn)
        try:
            while (await res.fetch_next()):
                item = await res.next()
                messages.append(await make_message(item))
            return messages
        finally:
            res.close()
```
That will allow us to make requests like
```
fragment MessageFragment on MessageType {
  id
  text
  createdAt
  userId
  channelId
}

query ALL_MESSAGES(
  $filter: JSON = null
  $page: Int = null
  $limit: Int = null
) {
  allMessages(filter: $filter, page: $page, limit: $limit) {
    ...MessageFragment
    users {
      id
      username
    }
    channels {
      id
      name
    }
  }
}

# Welcome to Altair GraphQL Client.
# You can send your request using CmdOrCtrl + Enter.

# Enter your graphQL query here.

mutation ADD_MESSAGE($input: AddMessageInput!){
  addMessage(input: $input) {
    createdAt
    userId
    channelId
    text
    id
    channels {
      name
    }
    users {
      username
    }
  }
}
```
But there is a better way to doing that so here come a new chalengers "DataLoader"
# DataLoader
It's a major feature that let you save resource and make the server happy. You can read more on that [here](https://github.com/graphql/dataloader) or as we using Strawberry [here](https://strawberry.rocks/docs/guides/dataloaders)
We have opting for the context version of the DataLoader but it's pretty and so convenient. Let take a look how how we can implement that
```
# server.py
# ...
class MyGraphQL(GraphQL):
    async def get_context(self, request: Union[Request, WebSocket],
                          response: Optional[Response]) -> Any:
        return {
            'user_loader': DataLoader(load_fn=load_users),   # We begining with users
        }

# models/users.py
async def load_users(keys: List[strawberry.ID]) -> Iterable[List[UserType]]:
    conn = await get_connection()
    cur = await r.table(userTbl).get_all(r.args(keys)).run(conn)
    try:
        users = await make_users(cur)
        groups = {k: [] for k in keys}
        for u in users:
            groups[u.id].append(u)
        return groups.values()
    finally:
        cur.close()
```
Now Strawberry with make sure to cache already loaded users and just using that version if no update occur. So let refine our definition of MessageType.
```
# models/messages.py
# ...
# dealing with cyclic import
if TYPE_CHECKING:
    from .channels import ChannelType
    from .users import UserType

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

# models/channels.py
# ...
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

# server.py
# ...
async def get_context(...):
    return {
        # ...
        'channel_loader': DataLoader(load_fn=load_channels),
    }
```
And with this update to our MessageQuery and MessageMutation
```
# models/messages.py
# ...
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
```
And Voila!!!
# So where to go now?
- Implements the AbstractCache of Strawberry to use Redis for caching;
- Adding Authentication and Authorization features;
- Implements the frontend

We will add all thoses sooner. Thank You for your times and happy coding.







