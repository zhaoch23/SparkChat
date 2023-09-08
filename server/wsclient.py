import base64
import datetime
import hashlib
import hmac
import json
import logging
import asyncio
from urllib.parse import urlparse
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

from typing import *

import websockets

class Ws_Param(object):
    # 初始化
    def __init__(self, appid, APIKey, APISecret, Spark_url, domain):
        self.apppid = appid
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.host = urlparse(Spark_url).netloc
        self.path = urlparse(Spark_url).path
        self.Spark_url = Spark_url
        self.domain = domain

    # 生成url
    def create_url(self):
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + self.host + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + self.path + " HTTP/1.1"

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()

        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", \
                                headers="host date request-line", signature="{signature_sha_base64}"'

        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }
        # 拼接鉴权参数，生成url
        url = self.Spark_url + '?' + urlencode(v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        logging.info(f"Created the request url: {url}")
        return url
    
def gen_params(appid, domain, questions: list[dict[str, str]], params=None) -> Any:
    """
    通过appid和用户的提问来生成请参数
    """
    if param is None:
        param = {
                "domain": domain,
                "temperature": 0.5,
                "max_tokens": 2048,
            }

    data = {
        "header": {
            "app_id": appid,
            "uid": "1234"
        },
        "parameter": {
            "chat": params
        },
        "payload": {
            "message": {
                "text": questions
            }
        }
    }
    return json.dumps(data)

def on_message(message) -> (int, str, dict):
    # print(message)
    data = json.loads(message)
    code = data['header']['code']
    if code != 0:
        logging.error(f'请求错误: {code}, {data}')
        return -1, "Erro code: " + str(code), {}
    else:
        choices = data["payload"]["choices"]
        status = choices["status"]
        content = choices["text"][0]["content"]
        logging.info(f"Decoded response msg content: {content}")
        
        metadata = data["payload"]["text"]
        total_tokens = metadata["total_tokens"]
        logging.info(f"{total_tokens} tokens used")
        # TODO: add the metadata
        return status, content, metadata
    

async def send_message(uri, msg, timeout=5.0) -> Any:
    async with websockets.connect(uri) as ws:
        await ws.send(msg)

        try:
            response = await asyncio.wait_for(ws.recv(), timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logging.error(f"Time out waiting for response from {uri}.")