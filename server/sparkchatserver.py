import asyncio
import logging
from typing import Any
from uuid import uuid4

import websockets

import config
from chatsession import ChatSession
from sparkclient import Ws_Param
import sparkchat_api_pb2 as api_pb2

async def echo(ws, **args):
    global server_instance
    async for data in ws:
        try:
            request = api_pb2.RequestWrapper()
            request.ParseFromString(data)

            response = api_pb2.ResponseWrapper()

            if request.HasField("open_session_request"):
                # Handle open session logic here
                res = await server_instance.on_open_session(request.on_session_request, 
                                                            response.open_session_response)

            elif request.HasField("chat_request"):
                # Handle chat logic here
                res = await server_instance.on_chat(request.chat_request, 
                                                    response.chat_response)

            elif request.HasField("chat_history_request"):
                # Handle chat history logic here
                res = await server_instance.on_chat_history(request.chat_history_request, 
                                                            response.chat_history_response)

            await ws.send(response.SerializeToString())
            logging.info("Response sent")

        except Exception as e:
            logging.error(f"Error handling request: {e}")

async def start_server(host, port):
    async with websockets.serve(echo, host, port):
        await asyncio.Future()  # run forever

class SparkChatServer(object):

    _ws_param_v1: Ws_Param
    _ws_param_v2: Ws_Param

    _connected_sessions: list[str]

    _chat_session_poll: dict[str, ChatSession]

    _lock: asyncio.Lock

    _session_history: dict[str, list[tuple[str, int, int]]]

    def __init__(self) -> None:
        self._connected_sessions = []
        self._chat_session_poll = {}
        self._lock = asyncio.Lock()
        self._ws_param_v1 = Ws_Param(
            config.appid,
            config.api_key,
            config.api_secret,
            config.Spark_url_v1,
            config.domain_v1
        )
        self._ws_param_v2 = Ws_Param(
            config.appid,
            config.api_key,
            config.api_secret,
            config.Spark_url_v2,
            config.domain_v2
        )

    def start(self):
        global server_instance
        if server_instance is None:
            server_instance = self
            logging.info(f"Starting server on ws://{config.server_host}:{config.server_port}")
            asyncio.get_event_loop().run_until_complete(start_server(config.server_host, config.server_port))
        else:
            raise RuntimeError("A server instance is running!")

    async def on_open_session(self, request, response) -> None:
        with self._lock:
            if request.HasField("client_id"):
                client_id = request.client_id
                if client_id not in self._connected_sessions:
                    self._connected_sessions.append(client_id)
                if client_id not in self._session_history:
                    self._session_history[client_id] = []
            else:
                client_id = str(uuid4())
                self._connected_sessions.append(client_id)
                self._session_history[client_id] = []
                response.client_id = client_id

            response.status = api_pb2.OpenSessionStatus.SESSION_STATUS_SUCCESS
            response.error_message = ""

    async def on_chat(self, request, response) -> None:
        if request.client_id not in self._connected_sessions:
            logging.warning(f"Client id {request.client_id} not registered!")
            response.status = api_pb2.ChatStatus.CHAT_STATUS_ERROR
            response.error_message = "Client id not registered!"
            return
        
        logging.info(f"Chat request from {response.client_id}")

        chat_title = request.chat_title
        chat_message = request.chat_message
        if chat_title not in self._chat_session_poll.keys:
            self._chat_session_poll[chat_title] = ChatSession()
        
        chat_session = self._chat_session_poll[chat_title]

        ws_param = self._ws_param_v1
        cut_histories = -1
        max_history_tokens = 8000
        gen_params = {
            "temperature": 0.5,
            "max_tokens": 2048
        }
        if request.HasField("params"):
            params = request.params
            if params.HasField("api_version") \
                and params.api_version == api_pb2.APIVersion.VERSION_2:
                    ws_param = self._ws_param_v2
            if params.HasField("cut_histories"):
                cut_histories = params.cut_histories
            if params.HasField("temperature"):
                gen_params["temperature"] = params.temperature
            if params.HasField("max_tokens"):
                gen_params["max_tokens"] = params.max_tokens
            if params.HasField("max_history_tokens"):
                max_history_tokens = params.max_history_tokens
        
        rec = await chat_session.chat(chat_message,
                                      ws_param,
                                      gen_params,
                                      cut_histories,
                                      max_history_tokens)
        
        if rec is None:
            response.status = api_pb2.ChatStatus.CHAT_STATUS_ERROR
            response.error_message = "Backend fault!"
            tp =  (chat_title, -1, chat_message.get_chat_history_length())
            logging.info(f"Request backend fault: {tp}")
            self._session_history[response.client_id].append(tp)
            return
        
        # Success replay
        if rec["status"] == 0:
            response.status = api_pb2.ChatStatus.CHAT_STATUS_BEGIN
        elif rec["status"] == 1:
            response.status = api_pb2.ChatStatus.CHAT_STATUS_MIDDLE
        elif rec["status"] == 2:
            response.status = api_pb2.ChatStatus.CHAT_STATUS_END
        
        response.details.formatted_timestamp = rec["timestamp"]
        response.details.status_code = rec["status"]
        response.details.role = rec["role"]
        response.details.tokens_spent = rec["tokens"]
        response.details.conetent = rec["content"]
        
        tp = (chat_title, rec["status"], chat_message.get_chat_history_length())
        self._session_history[response.client_id].append(tp)
        logging.info(f"Request success: {tp}")
            
    async def on_chat_history(self, request, response) -> Any:
        pass

server_instance: SparkChatServer = None