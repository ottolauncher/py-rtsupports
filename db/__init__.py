from rethinkdb import r
from rethinkdb.errors import ReqlOpFailedError
from utils.wrapper import run_once

userTbl = 'users'
channelTbl = 'channels'
messageTbl = 'messages'

r.set_loop_type('asyncio')


async def get_connection():
    return await r.connect(
        db='rtsupports',
        host='localhost'
    )


async def init():
    try:
        conn = await get_connection()
        r.table_create(userTbl).run(conn)
        r.table_create(channelTbl).run(conn)
        r.table_create(messageTbl).run(conn)

    except ReqlOpFailedError:
        pass


