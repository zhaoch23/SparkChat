import asyncio
import logging
from typing import Any

import websockets

import config
from chatsession import ChatSession
import sparkchat_api_pb2

async def echo(ws, **args):
    global server_instance
    async for data in ws:
        try:
            request = sparkchat_api_pb2.RequestWrapper()
            request.ParseFromString(data)

            if request.HasField("open_session_request"):
                # Handle open session logic here
                logging.info("Received open_session_request")
                response = await server_instance.on_open_session(request.on_session_request)

            elif request.HasField("chat_request"):
                # Handle chat logic here
                logging.info("Received chat_request")
                response = await server_instance.on_chat(request.chat_request)

            elif request.HasField("chat_history_request"):
                # Handle chat history logic here
                logging.info("Received chat_history_request")
                response = await server_instance.on_chat_history(request.chat_history)

            await ws.send(response.SerializeToString())
            logging.info("Response sent")

        except Exception as e:
            logging.error(f"Error handling request: {e}")

async def start_server(host, port):
    async with websockets.serve(echo, host, port):
        await asyncio.Future()  # run forever

class SparkChatServer(object):

    _connected_sessions: list[str]

    _chat_session_poll: dict[str, ChatSession]

    _lock: asyncio.Lock

    def __init__(self) -> None:
        self._connected_sessions = []
        self._chat_session_poll = {}
        self._lock = asyncio.Lock()

    def start(self):
        global server_instance
        if server_instance is None:
            server_instance = self
            logging.info(f"Starting server on ws://{config.server_host}:{config.server_port}")
            asyncio.get_event_loop().run_until_complete(start_server(config.server_host, config.server_port))
        else:
            raise RuntimeError("A server instance is running!")

    async def on_open_session(self, open_session_request) -> Any:
        with self._lock:
            pass

    async def on_chat(self, chat_request) -> Any:
        pass

    async def on_chat_history(self, chat_history_request) -> Any:
        pass

server_instance: SparkChatServer = None