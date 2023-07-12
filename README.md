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
According to the course we will need three models User, Channel and Message. The first approach of creating that like [Strawberry-Schema](https://strawberry.rocks/docs/types/schema)https://strawberry.rocks/docs/types/schema)
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
        pass
```


