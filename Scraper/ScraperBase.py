"""
All scraper MUST provide the same interface and the same result format.
"""
from urllib.parse import quote, unquote
from typing import Optional, Dict, Any


def fetch_content(
    url: str,
    timeout_ms: int,
    proxy: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Fetch web content from the specified url.
    :param url: The url to fetch.
    :param timeout_ms: The timeout in ms.
    :param proxy: The proxy setting. Currently, there are 2 kinds of proxy format. We're going to make them the same.
    :return:
        {
            'content': '',                  # The content in str. If it's an empty string, that means scrap fail.
            'errors': [''],                 # The error list in str
            'other optional fields': Any    # Any other extra fields that depends on scraper itself.
        }
    """
    return {
        'content': '',
        'errors': ['This is just an example of scraper implementation,'],

        'url': url,
        'timeout_ms': timeout_ms,
        'proxy': proxy
    }


def parse_proxy(proxy_input: dict) -> dict:
    """
    Universal proxy configuration parser supporting both Playwright and Requests formats.

    Args:
        proxy_input (dict): Input proxy configuration in either format:
            - Playwright format: {"server": "proto://host:port", "username": str, "password": str}
            - Requests format: {"http": "proto://[user:pass@]host:port", "https": ...}

    Returns:
        dict: Normalized proxy configuration:
            {
                "protocol": "http/socks5",    # Proxy protocol type
                "host": "127.0.0.1",          # Proxy server host
                "port": 10808,                # Proxy server port
                "username": "",               # Auth username (empty if no auth)
                "password": ""                # Auth password (empty if no auth)
            }
    """
    # Common defaults
    protocol = "http"
    host = "localhost"
    port = 80
    username = ""
    password = ""

    if "server" in proxy_input:  # Playwright format
        # Parse server URL
        server = proxy_input["server"]
        if "://" in server:
            protocol, remainder = server.split("://", 1)
        else:
            protocol, remainder = "http", server

        # Split host:port
        if ":" in remainder:
            host, port_str = remainder.split(":", 1)
            port = int(port_str)
        else:
            host = remainder

        # Get credentials
        username = proxy_input.get("username", "")
        password = proxy_input.get("password", "")

    else:  # Requests format
        # Get URL from either http or https key
        proxy_url = proxy_input.get("http") or proxy_input.get("https")
        if not proxy_url:
            raise KeyError("Invalid Requests proxy format - missing http/https keys")

        # Split protocol and remainder
        if "://" in proxy_url:
            protocol, remainder = proxy_url.split("://", 1)
        else:
            remainder = proxy_url

        # Extract auth and hostport
        if "@" in remainder:
            auth_part, hostport_part = remainder.split("@", 1)
            auth_components = auth_part.split(":", 1)
            username = unquote(auth_components[0])
            password = unquote(auth_components[1]) if len(auth_components) > 1 else ""
        else:
            hostport_part = remainder

        # Split host and port
        if ":" in hostport_part:
            host, port_str = hostport_part.split(":", 1)
            port = int(port_str)
        else:
            host = hostport_part

    return {
        "protocol": protocol,
        "host": host,
        "port": port,
        "username": username,
        "password": password
    }


def to_playwright(parsed_proxy: dict) -> dict:
    """
    Convert normalized config to Playwright-compatible proxy format.

    Args:
        parsed_proxy (dict): Normalized config from parse_proxy()

    Returns:
        dict: Playwright proxy configuration:
            {
                "server": "proto://host:port",
                "username": "",  # Explicit empty string if no auth
                "password": ""   # Explicit empty string if no auth
            }

    Notes:
        - Always includes username/password fields even when empty

    Examples:
        > to_playwright({'protocol': 'http', 'host': 'proxy', 'port': 8080})
        {'server': 'http://proxy:8080', 'username': '', 'password': ''}
    """
    return {
        "server": f"{parsed_proxy['protocol']}://{parsed_proxy['host']}:{parsed_proxy['port']}",
        "username": parsed_proxy["username"] if parsed_proxy["username"] else "",
        "password": parsed_proxy["password"] if parsed_proxy["password"] else ""
    }


def to_requests(parsed_proxy: dict) -> dict:
    """
    Convert normalized config to Requests-compatible proxy format.

    Args:
        parsed_proxy (dict): Normalized config from parse_proxy()

    Returns:
        dict: Requests proxy configuration:
            {
                "http": "proto://[auth@]host:port",
                "https": "proto://[auth@]host:port"
            }

    Notes:
        - Auth credentials are embedded in URL if present
        - Same configuration is copied to both http/https keys

    Examples:
        > to_requests({'protocol':'socks5','host':'1.1.1.1','port':1080})
        {'http': 'socks5://1.1.1.1:1080', 'https': 'socks5://1.1.1.1:1080'}
    """
    # 对用户名和密码进行URL编码（包括所有特殊字符）
    username = quote(parsed_proxy["username"], safe="")
    password = quote(parsed_proxy["password"], safe="")

    # 构建认证部分
    auth = f"{username}:{password}@" if parsed_proxy["username"] else ""

    # 生成完整的代理URL
    proxy_url = (
        f"{parsed_proxy['protocol']}://{auth}"
        f"{parsed_proxy['host']}:{parsed_proxy['port']}"
    )

    return {
        "http": proxy_url,
        "https": proxy_url
    }


# --------------------------
# Tests for parse_proxy()
# --------------------------
def test_parse_playwright_valid():
    # Standard case with auth
    input_conf = {"server": "socks5://proxy.com:1080", "username": "user", "password": "pass"}
    result = parse_proxy(input_conf)
    assert result == {
        "protocol": "socks5",
        "host": "proxy.com",
        "port": 1080,
        "username": "user",
        "password": "pass"
    }


def test_parse_playwright_no_auth():
    # No credentials
    input_conf = {"server": "http://localhost:8080", "username": "", "password": ""}
    result = parse_proxy(input_conf)
    assert result["username"] == "" and result["password"] == ""


def test_parse_requests_valid():
    # Standard Requests format
    input_conf = {"http": "socks5://user:pass@proxy.com:8888"}
    result = parse_proxy(input_conf)
    assert result["protocol"] == "socks5"
    assert result["host"] == "proxy.com"
    assert result["port"] == 8888


def test_parse_requests_special_chars():
    # Special characters in credentials
    input_conf = {"https": "http://user%40:pass%23@host:80"}
    result = parse_proxy(input_conf)
    assert result["username"] == "user@"
    assert result["password"] == "pass#"


def test_parse_missing_protocol():
    # Missing protocol (default to http)
    input_conf = {"server": "192.168.1.100:3128"}
    result = parse_proxy(input_conf)
    assert result["protocol"] == "http"
    assert result["host"] == "192.168.1.100"


def test_parse_invalid_port():
    # Non-numeric port
    try:
        parse_proxy({"server": "socks5://proxy.com:port"})
        assert False, "Should raise ValueError"
    except ValueError:
        pass


def test_parse_missing_server():
    # Invalid Playwright format
    try:
        parse_proxy({"username": "user"})
        assert False, "Should raise KeyError"
    except KeyError:
        pass


# --------------------------
# Tests for to_playwright()
# --------------------------
def test_to_playwright_normal():
    parsed = {
        "protocol": "http",
        "host": "proxy.com",
        "port": 8080,
        "username": "user",
        "password": "pass"
    }
    result = to_playwright(parsed)
    assert result == {
        "server": "http://proxy.com:8080",
        "username": "user",
        "password": "pass"
    }


def test_to_playwright_empty_auth():
    parsed = {
        "protocol": "socks5",
        "host": "localhost",
        "port": 1080,
        "username": "",
        "password": ""
    }
    result = to_playwright(parsed)
    assert result["username"] == "" and result["password"] == ""


def test_to_playwright_missing_fields():
    try:
        to_playwright({"host": "proxy.com"})
        assert False, "Should raise KeyError"
    except KeyError:
        pass


# --------------------------
# Tests for to_requests()
# --------------------------
def test_to_requests_normal():
    parsed = {
        "protocol": "socks5",
        "host": "proxy.com",
        "port": 1080,
        "username": "user",
        "password": "pass"
    }
    result = to_requests(parsed)
    assert result["http"] == "socks5://user:pass@proxy.com:1080"
    assert result["https"] == "socks5://user:pass@proxy.com:1080"


def test_to_requests_no_auth():
    parsed = {
        "protocol": "http",
        "host": "192.168.1.100",
        "port": 3128,
        "username": "",
        "password": ""
    }
    result = to_requests(parsed)
    assert "@" not in result["http"]
    assert result["http"] == "http://192.168.1.100:3128"


def test_to_requests_special_chars():
    parsed = {
        "protocol": "https",
        "host": "proxy.com",
        "port": 443,
        "username": "user@",
        "password": "pass:123"
    }
    result = to_requests(parsed)
    assert "user%40:pass%3A123" in result["https"]


def test_to_requests_missing_fields():
    try:
        to_requests({"protocol": "http"})
        assert False, "Should raise KeyError"
    except KeyError:
        pass


# --------------------------
# Run all tests
# --------------------------
def main():
    tests = [
        # parse_proxy tests
        test_parse_playwright_valid,
        test_parse_playwright_no_auth,
        test_parse_requests_valid,
        test_parse_requests_special_chars,
        test_parse_missing_protocol,
        test_parse_invalid_port,
        test_parse_missing_server,

        # to_playwright tests
        test_to_playwright_normal,
        test_to_playwright_empty_auth,
        test_to_playwright_missing_fields,

        # to_requests tests
        test_to_requests_normal,
        test_to_requests_no_auth,
        test_to_requests_special_chars,
        test_to_requests_missing_fields,
    ]

    for test in tests:
        print(f"Running {test.__name__}...")
        test()

    print("All tests passed!")


if __name__ == "__main__":
    main()
