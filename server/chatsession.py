from typing import *

from wsclient import *

class ChatSession(object):

    """
    {
        "status": 0, # -1 for error, 0 for chat begin, 1 for in middle chat, 2 for end
        "role": "assitant",
        "content": "msg"
        "tokens": 100
    }
    """
    _chat_history: list[dict[str, str | int]]

    _ws_params: Ws_Param

    _token_spent: int

    def __init__(self, ws_param: Ws_Param) -> None:
        self._ws_params = ws_param
        self._chat_history = []
        self._token_spent = 0
    
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

        for msg in self._chat_history:
            tmp = tmp + "Status: {:<10}, Role: {:<10}, Tokens: {:<10}, Content: {}" \
               .format(msg["status"], msg["role"], msg["tokens"], msg["content"]) + "\n"
        
        return tmp[:-1]
    
    def get_token_spent(self) -> int:
        return sum([msg["tokens"] for msg in self._chat_history])

    def _prepair_questions(self, user_msg, cut_histories) -> list[dict[str, str]]:
        if cut_histories == -1:
            cut_histories = len(self.get_chat_history_length())



    def _add_chat_history(self, status, role, content, tokens=0):
        msg = {}
        msg["status"] = status
        msg["role"] = role
        msg["content"] = content
        msg["tokens"] = tokens
        self._chat_history.append(msg)
    
    async def chat(self, user_msg, cut_histories=-1) -> str | None:
        """
        """
        if self.is_closed():
            res = f"User tries to chat with session id {id(self)}, but the session was closed!"
            logging.warning(res)
            return res

        if len(self._chat_history) == 0:
            self._add_chat_history(0, "user", user_msg)
        else:
            self._add_chat_history(1, "user", user_msg)

        questions = self._prepair_questions(user_msg, cut_histories)
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