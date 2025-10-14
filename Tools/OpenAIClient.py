import os
import json
import threading

import requests
from typing import Optional, Dict, Any, Union, List

try:
    import aiohttp
except:
    aiohttp = None


"""
Siliconflow Reply example:
{
  "id": "0196f08d74220b683a08ca3630683a51",         # 唯一标识符，用于追踪API调用记录
  "object": "chat.completion",                      # 标识响应类型，chat.completion表示这是聊天补全类型的响应
  "created": 1747792524,                            # Unix时间戳，表示API请求处理完成的时间（示例值1747792524对应北京时间2025-05-21 15:55:24）
  "model": "Qwen/Qwen3-235B-A22B",                  # 实际使用的模型标识，示例中Qwen/Qwen3-235B-A22B表明调用了第三方适配的千问模型
  "choices": [                                      # 包含生成结果的容器，常规场景下仅有一个元素
    {
      "index": 0,                                   # 候选结果的序号（多候选时有效）
      "message": {                                  # 生成的对话消息对象
        "role": "assistant",                        # 消息来源标识（assistant表示AI生成）
        "content": ""                               # 实际生成的文本内容 <-- **需要关注该内容**
		},
      "finish_reason": "stop"                       # 生成终止原因，"stop"表示自然结束
    }
  ],
  "usage": {                                        # 资源消耗统计
    "prompt_tokens": 22,                            # 输入消耗的token数
    "completion_tokens": 254,                       # 输出消耗的token数
    "total_tokens": 276,                            # 总token数
    "completion_tokens_details": {                  # 扩展字段
      "reasoning_tokens": 187                       # 推理过程消耗的token数
    }
  },
  "system_fingerprint": ""                          # 系统指纹标识，用于追踪模型版本信息（示例为空说明未启用该功能）
}
"""


class OpenAICompatibleAPI:
    """
    A client class to interact with OpenAI-like API services.

    This class provides a flexible way to communicate with APIs that are compatible with OpenAI's interface.
    It supports both synchronous and asynchronous requests and provides token authentication handling.

    Attributes:
        api_base_url (str): The base URL of the API service.
        api_token (str): Authentication token for the API.
        default_model (str): Default model to use when making requests.
    """

    def __init__(self, api_base_url: str, token: Optional[str] = None,
                 default_model: str = "gpt-3.5-turbo", proxies: dict = None):
        """
        Initialize the OpenAI-compatible API client.

        Args:
            api_base_url (str): The base URL of the API service.
            token (Optional[str]): Authentication token for the API. If not provided, it will be fetched from environment variables.
            default_model (str): Default model to use when making requests.

        Raises:
            ValueError: If token is not provided and not found in environment variables.
        """
        self.api_base_url = api_base_url.strip()

        # Try to get token from environment variables if not provided
        self.api_token = token or os.getenv("OPENAI_API_KEY")

        if not self.api_token:
            raise ValueError(
                "API token must be provided either through the constructor or environment variable OPENAI_API_KEY")

        self.default_model = default_model
        self.proxies = proxies or {}
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }
        self.lock = threading.Lock()

    def _construct_url(self, endpoint: str) -> str:
        """Construct the full URL for a given API endpoint."""
        base = self.api_base_url.rstrip('/')
        return f"{base}/{endpoint}"

    def _prepare_request_data(self,
                              model: Optional[str] = None,
                              messages: Optional[List[Dict[str, str]]] = None,
                              **kwargs) -> Dict[str, Any]:
        """
        Prepare data for the API request.

        Args:
            model (Optional[str]): Model to use for the request. Defaults to the client's_model default.
            messages (Optional[List[Dict[str, str]]]): List of message objects for chat completion.
            **kwargs: Additional parameters to include in the request.

        Returns:
            Dict[str, Any]: Prepared request data.
        """
        request_data = {
            "model": model or self.default_model,
            **kwargs
        }

        # Add messages if provided for chat completion
        if messages:
            request_data["messages"] = messages

        return request_data

    def set_api_token(self, token: str):
        with self.lock:
            self.api_token = token
            self.headers["Authorization"] = f"Bearer {self.api_token}"
            
    def get_header(self) -> dict:
        with self.lock:
            return self.headers.copy()

    def get_model_list(self) -> Union[Dict[str, Any], requests.Response]:
        """
        Get the list of available models from the API.

        Returns:
            Union[Dict[str, Any], requests.Response]: The API response, either as a parsed dictionary or the raw response object.
        """
        url = self._construct_url("models")
        if self.proxies:
            response = requests.get(url, headers=self.get_header(), proxies=self.proxies)
        else:
            response = requests.get(url, headers=self.get_header())
        return response.json() if response.status_code == 200 else response

    def create_chat_completion_sync(self,
                                    messages: List[Dict[str, str]],
                                    model: Optional[str] = None,
                                    temperature: float = 0.7,
                                    max_tokens: int = 4096) -> Union[Dict[str, Any], requests.Response]:
        """
        Create a chat completion synchronously.

        Args:
            messages (List[Dict[str, str]]): List of message objects for the conversation.
            model (Optional[str]): Model to use for the completion. Defaults to the client's default_model.
            temperature (float): Controls randomness. Lower values give more deterministic results.
            max_tokens (int): Maximum number of tokens to generate in the response.

        Returns:
            Union[Dict[str, Any], requests.Response]: The API response, either as a parsed dictionary or the raw response object.

        Note:
            The messages should be in the format of [{"role": "system", "content": "System message"},
                                                   {"role": "user", "content": "User message"}].
        """
        url = self._construct_url("chat/completions")
        data = self._prepare_request_data(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Use POST request to send the completion request
        response = requests.post(url, headers=self.get_header(), json=data, proxies=self.proxies)

        # Return parsed JSON if successful, otherwise return the raw response
        return response.json() if response.status_code == 200 else response

    async def create_chat_completion_async(self,
                                           messages: List[Dict[str, str]],
                                           model: Optional[str] = None,
                                           temperature: float = 0.7,
                                           max_tokens: int = 4096) -> Dict[str, Any]:
        """
        Create a chat completion asynchronously.

        Args:
            messages (List[Dict[str, str]]): List of message objects for the conversation.
            model (Optional[str]): Model to use for the completion. Defaults to the client's default_model.
            temperature (float): Controls randomness. Lower values give more deterministic results.
            max_tokens (int): Maximum number of tokens to generate in the response.

        Returns:
            Dict[str, Any]: The API response as a parsed dictionary.

        Note:
            Requires asyncio and aiohttp to be installed and used within an async context.
            The messages should be in the format of [{"role": "system", "content": "System message"},
                                                   {"role": "user", "content": "User message"}].
        """
        if not aiohttp:
            return {}

        url = self._construct_url("chat/completions")
        data = self._prepare_request_data(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Use async POST request to send the completion request
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.get_header(), json=data, proxy=self._get_url_proxy(url)) as response:
                return await response.json()

    def create_completion_sync(self,
                               prompt: str,
                               model: Optional[str] = None,
                               temperature: float = 0.7,
                               max_tokens: int = 4096) -> Union[Dict[str, Any], requests.Response]:
        """
        Create a text completion synchronously.

        Args:
            prompt (str): The text prompt to generate completion for.
            model (Optional[str]): Model to use for the completion. Defaults to the client's default_model.
            temperature (float): Controls randomness. Lower values give more deterministic results.
            max_tokens (int): Maximum number of tokens to generate in the response.

        Returns:
            Union[Dict[str, Any], requests.Response]: The API response, either as a parsed dictionary or the raw response object.
        """
        url = self._construct_url("completions")
        data = self._prepare_request_data(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Use POST request to send the completion request
        response = requests.post(url, headers=self.get_header(), json=data, proxies=self.proxies)

        # Return parsed JSON if successful, otherwise return the raw response
        return response.json() if response.status_code == 200 else response

    async def create_completion_async(self,
                                      prompt: str,
                                      model: Optional[str] = None,
                                      temperature: float = 0.7,
                                      max_tokens: int = 4096) -> Dict[str, Any]:
        """
        Create a text completion asynchronously.

        Args:
            prompt (str): The text prompt to generate completion for.
            model (Optional[str]): Model to use for the completion. Defaults to the client's default_model.
            temperature (float): Controls randomness. Lower values give more deterministic results.
            max_tokens (int): Maximum number of tokens to generate in the response.

        Returns:
            Dict[str, Any]: The API response as a parsed dictionary.

        Note:
            Requires asyncio and aiohttp to be installed and used within an async context.
        """
        if not aiohttp:
            return {}

        url = self._construct_url("completions")
        data = self._prepare_request_data(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Use async POST request to send the completion request
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.get_header(), json=data, proxy=self._get_url_proxy(url)) as response:
                return await response.json()

    def _get_url_proxy(self, url: str) -> Optional[str]:
        if not self.proxies:
            return None
        return self.proxies.get("https") if url.startswith("https") else self.proxies.get("http")


# ----------------------------------------------------------------------------------------------------------------------

def create_ollama_client():
    client = OpenAICompatibleAPI(
        api_base_url='http://localhost:11434/v1',
        token='x',
        default_model='qwen3:14b'
    )
    return client


def create_siliconflow_client():
    client = OpenAICompatibleAPI(
        api_base_url='https://api.siliconflow.cn/v1',
        token=os.getenv("SILICON_API_KEY"),
        default_model='Qwen/Qwen3-235B-A22B'
    )
    return client


def create_gemini_client():
    client = OpenAICompatibleAPI(
        api_base_url='https://generativelanguage.googleapis.com/v1beta/openai',
        token=os.getenv("GEMINI_API_KEY"),
        default_model='models/gemini-pro-latest',
        proxies={
            "http": "http://127.0.0.1:10809",
            "https": "http://127.0.0.1:10809"
        }
    )
    return client


def main():
    try:
        from MyPythonUtility.DictTools import DictPrinter
    except Exception as e:
        print(str(e))
        DictPrinter = None
    finally:
        pass

    # Initialize the client - token can be passed directly or will be fetched from environment
    client = create_gemini_client()

    model_list = client.get_model_list()
    print(f'Model list of {client.api_base_url}')

    if isinstance(model_list, dict) and DictPrinter:
        print(DictPrinter.pretty_print(model_list))
    else:
        print(model_list)

    # Example synchronous chat completion
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你是谁?"}
    ]

    response = client.create_chat_completion_sync(messages=messages)
    print("Synchronous chat completion response:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    # # Example synchronous text completion
    # prompt = "Once upon a time in a land far away,"
    # response = client.create_completion_sync(prompt=prompt)
    # print("\nSynchronous text completion response:")
    # print(json.dumps(response, indent=2))

    # Example asynchronous usage requires asyncio
    import asyncio


    async def async_demo():
        # Example async chat completion
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the meaning of life?"}
        ]

        response = await client.create_chat_completion_async(messages=messages)
        print("\nAsynchronous chat completion response:")
        print(json.dumps(response, indent=2))

        # Example async text completion
        prompt = "The capital of France is"
        response = await client.create_completion_async(prompt=prompt)
        print("\nAsynchronous text completion response:")
        print(json.dumps(response, indent=2))


    # Run the async demo
    asyncio.run(async_demo())


# Example usage
if __name__ == "__main__":
    main()
