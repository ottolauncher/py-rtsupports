import asyncio
import uvicorn
from typing import Optional, Union, Any
from strawberry.dataloader import DataLoader
from starlette.requests import Request
from starlette.websockets import WebSocket
from starlette.responses import Response
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from strawberry.asgi import GraphQL
from api import schema
import settings
from db import init
from models.channels import load_channels, load_channels_by_message
from models.messages import load_messages_by_channel, load_get_message
from models.users import load_users, load_users_by_message
from utils.wrapper import run_once


class MyGraphQL(GraphQL):
    async def get_context(self, request: Union[Request, WebSocket],
                          response: Optional[Response]) -> Any:
        return {
            'user_loader': DataLoader(load_fn=load_users),
            'channel_loader': DataLoader(load_fn=load_channels),
            'messages_by_channel': DataLoader(load_fn=load_messages_by_channel),
            'channels_by_message': DataLoader(load_fn=load_channels_by_message),
            'users_by_message': DataLoader(load_fn=load_users_by_message),
            'message_loader': DataLoader(load_fn=load_get_message)
        }


graphql_app = MyGraphQL(schema=schema)

routes = [
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
