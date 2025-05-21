import os
import json
import requests
from typing import Optional, Dict, Any, Union, List


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

    def __init__(self, api_base_url: str, token: Optional[str] = None, default_model: str = "gpt-3.5-turbo"):
        """
        Initialize the OpenAI-compatible API client.

        Args:
            api_base_url (str): The base URL of the API service.
            token (Optional[str]): Authentication token for the API. If not provided, it will be fetched from environment variables.
            default_model (str): Default model to use when making requests.

        Raises:
            ValueError: If token is not provided and not found in environment variables.
        """
        self.api_base_url = api_base_url

        # Try to get token from environment variables if not provided
        self.api_token = token or os.getenv("OPENAI_API_KEY")

        if not self.api_token:
            raise ValueError(
                "API token must be provided either through the constructor or environment variable OPENAI_API_KEY")

        self.default_model = default_model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }

    def _construct_url(self, endpoint: str) -> str:
        """Construct the full URL for a given API endpoint."""
        return f"{self.api_base_url}/v1/{endpoint}"

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

    def get_model_list(self) -> Union[Dict[str, Any], requests.Response]:
        """
        Get the list of available models from the API.

        Returns:
            Union[Dict[str, Any], requests.Response]: The API response, either as a parsed dictionary or the raw response object.
        """
        url = self._construct_url("models")
        response = requests.get(url, headers=self.headers)
        return response.json() if response.status_code == 200 else response

    def create_chat_completion_sync(self,
                                    messages: List[Dict[str, str]],
                                    model: Optional[str] = None,
                                    temperature: float = 0.7,
                                    max_tokens: int = 150) -> Union[Dict[str, Any], requests.Response]:
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
        response = requests.post(url, headers=self.headers, json=data)

        # Return parsed JSON if successful, otherwise return the raw response
        return response.json() if response.status_code == 200 else response

    async def create_chat_completion_async(self,
                                           messages: List[Dict[str, str]],
                                           model: Optional[str] = None,
                                           temperature: float = 0.7,
                                           max_tokens: int = 150) -> Dict[str, Any]:
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
        import aiohttp

        url = self._construct_url("chat/completions")
        data = self._prepare_request_data(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Use async POST request to send the completion request
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=data) as response:
                return await response.json()

    def create_completion_sync(self,
                               prompt: str,
                               model: Optional[str] = None,
                               temperature: float = 0.7,
                               max_tokens: int = 150) -> Union[Dict[str, Any], requests.Response]:
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
        response = requests.post(url, headers=self.headers, json=data)

        # Return parsed JSON if successful, otherwise return the raw response
        return response.json() if response.status_code == 200 else response

    async def create_completion_async(self,
                                      prompt: str,
                                      model: Optional[str] = None,
                                      temperature: float = 0.7,
                                      max_tokens: int = 150) -> Dict[str, Any]:
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
        import aiohttp

        url = self._construct_url("completions")
        data = self._prepare_request_data(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Use async POST request to send the completion request
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=data) as response:
                return await response.json()


def main():
    # Set your API base URL
    API_BASE_URL = "https://api.siliconflow.cn"

    # Initialize the client - token can be passed directly or will be fetched from environment
    client = (OpenAICompatibleAPI
              (api_base_url=API_BASE_URL,
               token='',
               default_model='Qwen/Qwen3-235B-A22B'))

    model_list = client.get_model_list()
    print(f'Model list of {API_BASE_URL}')
    print('\n'.join(model_list))

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
