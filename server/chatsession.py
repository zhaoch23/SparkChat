from typing import *
from datetime import datetime

from sparkclient import *

class ChatSession(object):

    """ Sample element in _chat_history:
    {
        "timestamp": datetime object
        "status": 0, # -1 for error, 0 for chat begin, 1 for in middle chat, 2 for end
        "role": "assitant",
        "tokens": 100,
        "content": "msg"
    }
    """
    _chat_history: list[dict[str, datetime | str | int]]

    _ws_params: Ws_Param

    _token_spent: int

    _lock: asyncio.Lock

    def __init__(self, ws_param: Ws_Param) -> None:
        self._ws_params = ws_param
        self._chat_history = []
        self._token_spent = 0
        self._lock = asyncio.Lock()
    
    def is_closed(self) -> bool:
        if len(self._chat_history) > 0:
            return self._chat_history[-1]["status"] == 2
        
        return False
    
    def get_chat_histories(self) -> list[dict[str, str | int]]:
        # return a duplicated list
        return [chat.copy() for chat in self._chat_history]

    def get_last_chat_msg(self) -> dict[str, str | int]:
        if len(self._chat_history) > 0:
            return self._chat_history[-1].copy()
        
        return None
    
    def get_chat_history_length(self) -> int:
        return len(self._chat_history)
    
    def get_chat_history_strings(self, length=-1) -> str:
        tmp = ""

        for msg in reversed(self._chat_history):
            tmp = "[{}] Status: {:<10}, Role: {:<10}, Tokens: {:<10}, Content: {}" \
               .format(msg["timestamp"].strftime("%m/%d/%Y, %H:%M:%S"), msg["status"], 
                       msg["role"], msg["tokens"], msg["content"])  + "\n" + tmp
        
        return tmp[:-1]
    
    def get_chat_history_simplified(self, length=-1) -> list[dict[str, str | int]]:
        records = self.get_chat_histories()
        for rec in records:
            rec["timestamp"] = rec["timestamp"].strftime("%m/%d/%Y, %H:%M:%S")
        return records
    
    def get_token_spent(self) -> int:
        return sum([msg["tokens"] for msg in self._chat_history])

    def _prepair_prompts(self, user_msg, cut_histories) -> list[dict[str, str]]:
        """
        This function will prepare the prompts for the generation
        with historical chat records

        Return sample:
        .. highlight:: python
        .. code-block:: python
        [
            {"role": "user", "content": "你是谁"} # 用户的历史问题
            {"role": "assistant", "content": "....."}  # AI的历史回答结果
            # ....... 省略的历史对话
            {"role": "user", "content": "你会做什么"}  # 最新的一条问题，如无需上下文，可只传最新一条问题
        ]
 
        """
        if cut_histories == -1:
            cut_histories = len(self.get_chat_history_length())
        
        prepaired_prompts = []
        i = 0
        for record in reversed(self._chat_history):
            if i >= cut_histories:
                break
            
            if record["status"] != -1:
                prompt = {}
                prompt["role"] = record["role"]
                prompt["content"] = record["content"]
                prepaired_prompts.append(prompt)
                i += 1
            
        prepaired_prompts.append({"role": "user", "content": user_msg})

        return prepaired_prompts.reverse()

    def _add_chat_history(self, status, role, content, tokens=0):
        msg = {}
        msg["timestamp"] = datetime.now()
        msg["status"] = status
        msg["role"] = role
        msg["content"] = content
        msg["tokens"] = tokens
        self._chat_history.append(msg)
    
    async def chat(self, user_msg, cut_histories=-1) -> str | None:
        """ Chat with the AI. One chat at a time.
        """
        if self.is_closed():
            res = f"User tries to chat with session id {id(self)}, but the session was closed!"
            logging.warning(res)
            return res
        
        with self._lock:
            if len(self._chat_history) == 0:
                self._add_chat_history(0, "user", user_msg)
            else:
                self._add_chat_history(1, "user", user_msg)

            questions = self._prepair_prompts(user_msg, cut_histories)
            request = gen_params(self._ws_params.apppid, self._ws_params.domain, questions)

            response = await send_message(self._ws_params.create_url, request)

            if response is None:
                self._add_chat_history(-1, "assistant", "Error in request: Timed out!")
                return None
            
            status, content, metadata = on_message(response)

            if status == -1: # Error code
                self._add_chat_history(status, "assistant", content)
                logging.error(f"Error in response: {content}")
                return None
            
            self._add_chat_history(status, "assistant", content, metadata["total_tokens"])

            return content