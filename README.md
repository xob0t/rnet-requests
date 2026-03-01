# rnet-requests

A **requests-compatible** and **curl_cffi-compatible** API wrapper for [rnet](https://github.com/0x676e67/rnet) - the blazing-fast Python HTTP client with advanced browser fingerprinting.

Drop-in replacement for `requests` or `curl_cffi`, powered by rnet's Rust-based engine with TLS fingerprint impersonation for Chrome, Firefox, Safari, Edge, and more.

## Features

- **Familiar API**: Use the same `requests`-style interface you already know
- **curl_cffi Compatible**: Supports curl_cffi patterns like `base_url`, `Headers`, `Cookies` classes
- **Async Support**: Full async/await support with `AsyncSession`
- **WebSocket Support**: Async WebSocket connections with `ws_connect()`
- **Browser Impersonation**: Automatically mimic browser TLS/HTTP2 fingerprints
- **High Performance**: Powered by rnet's Rust-based async engine
- **Cookie Persistence**: Session-based cookie management
- **Connection Pooling**: Efficient connection reuse
- **Full Type Hints**: Complete type annotations for IDE support

## Installation

```bash
pip install rnet-requests
```

Or with uv:

```bash
uv add rnet-requests
```

## Quick Start

### Simple Requests (Sync)

```python
import rnet_requests as requests

# GET request
r = requests.get('https://httpbin.org/get')
print(r.status_code)  # 200
print(r.json())       # {'args': {}, ...}

# POST request with JSON
r = requests.post('https://httpbin.org/post', json={'key': 'value'})
print(r.json())

# POST request with form data
r = requests.post('https://httpbin.org/post', data={'key': 'value'})

# Custom headers
r = requests.get('https://httpbin.org/headers', headers={'X-Custom': 'value'})
```

### Async Requests

```python
import asyncio
import rnet_requests as requests

async def main():
    # Simple async GET
    r = await requests.async_get('https://httpbin.org/get')
    print(r.status_code)  # 200
    print(r.json())

    # Using AsyncSession for multiple requests
    async with requests.AsyncSession(impersonate='chrome') as s:
        r = await s.get('https://httpbin.org/get')
        print(r.json())
        
        # Concurrent requests
        tasks = [
            s.get('https://httpbin.org/get?id=1'),
            s.get('https://httpbin.org/get?id=2'),
            s.get('https://httpbin.org/get?id=3'),
        ]
        responses = await asyncio.gather(*tasks)
        for r in responses:
            print(r.json())

asyncio.run(main())
```

### Browser Impersonation

The killer feature - make requests that look like they're coming from real browsers:

```python
import rnet_requests as requests

# Impersonate Chrome (sync)
r = requests.get('https://tls.peet.ws/api/all', impersonate='chrome')
print(r.json()['tls']['ja3_hash'])  # Chrome's JA3 fingerprint

# Impersonate Firefox (async)
r = await requests.async_get('https://tls.peet.ws/api/all', impersonate='firefox')

# Available impersonation options:
# 'chrome', 'firefox', 'safari', 'edge', 'opera', 'okhttp'
# Specific versions are auto-detected from rnet (e.g., Chrome136, Firefox139, Safari18)
```

### OS Impersonation

Control the operating system fingerprint in addition to browser:

```python
import rnet_requests as requests

# Impersonate Chrome on Windows
with requests.Session(impersonate='chrome', impersonate_os='windows') as s:
    r = s.get('https://httpbin.org/headers')
    # User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...

# Impersonate Chrome on macOS
with requests.Session(impersonate='chrome', impersonate_os='macos') as s:
    r = s.get('https://httpbin.org/headers')
    # User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...

# Impersonate Safari on iOS
with requests.Session(impersonate='safari', impersonate_os='ios') as s:
    r = s.get('https://httpbin.org/headers')

# Available OS options:
# 'windows', 'macos', 'linux', 'android', 'ios'

# Async session with OS impersonation
async with requests.AsyncSession(impersonate='firefox', impersonate_os='linux') as s:
    r = await s.get('https://httpbin.org/headers')
```

### Using Sessions

Sessions persist settings and cookies across requests:

```python
import rnet_requests as requests

# Sync Session with Chrome impersonation
with requests.Session(impersonate='chrome') as s:
    # Login (cookies are automatically saved)
    s.post('https://httpbin.org/cookies/set/session/abc123')
    
    # Subsequent requests include cookies
    r = s.get('https://httpbin.org/cookies')
    print(r.json())  # {'cookies': {'session': 'abc123'}}

# Async Session
async with requests.AsyncSession(impersonate='firefox') as s:
    await s.get('https://httpbin.org/cookies/set/session/xyz789')
    r = await s.get('https://httpbin.org/cookies')
    print(r.json())
```

## curl_cffi Compatible Features

### Base URL

Use `base_url` for APIs with a common base path:

```python
import rnet_requests as requests

# All requests will be relative to base_url
with requests.Session(base_url='https://api.example.com/v1') as s:
    r = s.get('/users')        # GET https://api.example.com/v1/users
    r = s.get('/users/123')    # GET https://api.example.com/v1/users/123
    r = s.post('/users', json={'name': 'John'})

# Works with async too
async with requests.AsyncSession(base_url='https://api.example.com/v1') as s:
    r = await s.get('/users')
```

### Default Query Parameters

Set default params that apply to all requests:

```python
import rnet_requests as requests

# API key added to every request
with requests.Session(params={'api_key': 'secret123'}) as s:
    r = s.get('https://api.example.com/data')  
    # GET https://api.example.com/data?api_key=secret123
    
    r = s.get('https://api.example.com/data', params={'page': 1})  
    # GET https://api.example.com/data?api_key=secret123&page=1
```

### Proxy Shorthand

Use `proxy` parameter for simple proxy configuration:

```python
import rnet_requests as requests

# Single proxy for all requests
with requests.Session(proxy='http://proxy.example.com:8080') as s:
    r = s.get('https://httpbin.org/ip')

# Or use proxies dict for protocol-specific proxies
with requests.Session(proxies={
    'http': 'http://proxy1:8080',
    'https': 'http://proxy2:8080'
}) as s:
    r = s.get('https://httpbin.org/ip')
```

### Headers Class

curl_cffi-compatible Headers class with multi-value support:

```python
from rnet_requests import Headers

# Create headers
headers = Headers({
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})

# Case-insensitive access
print(headers['content-type'])  # 'application/json'

# Multi-value support
headers = Headers([
    ('Set-Cookie', 'a=1'),
    ('Set-Cookie', 'b=2'),
])
print(headers.get_list('Set-Cookie'))  # ['a=1', 'b=2']

# Split comma-separated values
headers = Headers({'Accept': 'text/html, application/json'})
print(headers.get_list('Accept', split_commas=True))  
# ['text/html', 'application/json']

# Iterate over all header pairs
for key, value in headers.multi_items():
    print(f'{key}: {value}')
```

### Cookies Class

curl_cffi-compatible Cookies class with domain support:

```python
from rnet_requests import Cookies

# Create cookies
cookies = Cookies({'session': 'abc123'})

# Set with domain/path
cookies.set('token', 'xyz', domain='.example.com', path='/')

# Get cookies for specific domain
cookies.get('token', domain='.example.com')

# Get all cookies as dict
cookies.get_dict()
cookies.get_dict(domain='.example.com')

# Delete specific cookie
cookies.delete('session')
cookies.delete('token', domain='.example.com')

# Clear all
cookies.clear()
```

### Multipart Form Data

Easy file uploads with the Multipart class:

```python
from rnet_requests import Multipart, Session

# Create multipart form data
mp = Multipart()
mp.addpart('field', data=b'value')
mp.addpart('file', filename='report.csv', data=b'a,b,c\n1,2,3')
mp.addpart('image', filename='photo.png', data=open('photo.png', 'rb').read(),
           content_type='image/png')

# Or load from file path
mp.addpart('document', local_path='./document.pdf')

# Send with session
with Session() as s:
    r = s.post('https://httpbin.org/post', multipart=mp)

# Or create from dict
mp = Multipart.from_dict({
    'field': 'value',
    'file': ('report.csv', b'a,b,c\n1,2,3', 'text/csv'),
})
```

### Initial Cookies

Pass cookies when creating a session:

```python
import rnet_requests as requests

# Session with initial cookies
with requests.Session(cookies={'session': 'abc123', 'user': 'john'}) as s:
    r = s.get('https://httpbin.org/cookies')
    print(r.json())  # {'cookies': {'session': 'abc123', 'user': 'john'}}
```

## WebSocket Support

Async WebSocket connections:

```python
import asyncio
from rnet_requests import AsyncSession

async def main():
    async with AsyncSession() as session:
        # Connect to WebSocket
        async with session.ws_connect('wss://echo.websocket.org') as ws:
            # Send text message
            await ws.send_str('Hello, WebSocket!')
            
            # Receive text message
            msg = await ws.recv_str()
            print(msg)  # 'Hello, WebSocket!'
            
            # Send/receive JSON
            await ws.send_json({'type': 'ping'})
            data = await ws.recv_json()
            
            # Send binary data
            await ws.send_bytes(b'\x00\x01\x02')
            
            # Receive with timeout
            try:
                msg = await ws.recv_str(timeout=5.0)
            except WebSocketTimeout:
                print('Timed out')

asyncio.run(main())
```

## Advanced Usage

### Retry Strategy

Configure automatic retries for failed requests:

```python
import rnet_requests as requests
from rnet_requests import RetryStrategy

# Simple retry count
with requests.Session(retry=3) as s:
    r = s.get('https://httpbin.org/get')

# Advanced retry configuration
strategy = RetryStrategy(
    count=3,           # Number of retries
    delay=1.0,         # Base delay between retries (seconds)
    jitter=0.5,        # Random jitter to add (0 to 0.5 seconds)
    backoff='exponential',  # 'linear' or 'exponential'
)
with requests.Session(retry=strategy) as s:
    r = s.get('https://httpbin.org/get')

# Also works with async
async with requests.AsyncSession(retry=strategy) as s:
    r = await s.get('https://httpbin.org/get')
```

### Auto Raise for Status

Automatically raise HTTPError for 4xx/5xx responses:

```python
import rnet_requests as requests
from rnet_requests.exceptions import HTTPError

with requests.Session(raise_for_status=True) as s:
    try:
        r = s.get('https://httpbin.org/status/404')
    except HTTPError as e:
        print(f"Error: {e}")  # Error: 404 Client Error: Not Found
```

### Referer Shortcut

Easily set the Referer header:

```python
import rnet_requests as requests

with requests.Session() as s:
    r = s.get('https://httpbin.org/headers', referer='https://google.com')
    print(r.json()['headers']['Referer'])  # https://google.com
```

### Browser and OS Impersonation

```python
import rnet_requests as requests
from rnet import Emulation, EmulationOption, EmulationOS

# Use specific browser version with OS using rnet's native types
s = requests.Session(
    impersonate=EmulationOption(
        Emulation.Chrome136,
        emulation_os=EmulationOS.Windows,
    )
)

# Or use the simple string API (recommended)
s = requests.Session(impersonate='chrome', impersonate_os='windows')

# Timeout configuration
r = requests.get('https://httpbin.org/delay/5', timeout=10)

# Or with separate connect/read timeouts
r = requests.get('https://httpbin.org/delay/5', timeout=(5, 30))

# Disable redirects
r = requests.get('https://httpbin.org/redirect/3', allow_redirects=False)
print(r.status_code)  # 302

# Basic authentication
r = requests.get('https://httpbin.org/basic-auth/user/pass', auth=('user', 'pass'))

# File upload (requests-style)
files = {'file': ('report.csv', open('report.csv', 'rb'), 'text/csv')}
r = requests.post('https://httpbin.org/post', files=files)

# Proxy configuration
r = requests.get('https://httpbin.org/ip', proxies={'https': 'http://proxy:8080'})
```

## Response Object

The Response object is compatible with `requests.Response`:

```python
import rnet_requests as requests

r = requests.get('https://httpbin.org/get')

# Status
r.status_code      # 200
r.ok               # True
r.reason           # 'OK'

# Content
r.text             # Response as string
r.content          # Response as bytes
r.json()           # Parse JSON response

# Headers
r.headers          # Case-insensitive dict
r.headers['Content-Type']

# Cookies
r.cookies          # Dict of cookies

# URL (after redirects)
r.url              # Final URL

# Raise exception for 4xx/5xx
r.raise_for_status()
```

## Exception Handling

```python
import rnet_requests as requests
from rnet_requests import (
    RequestException,
    ConnectionError,
    Timeout,
    HTTPError,
)

try:
    r = requests.get('https://httpbin.org/status/404')
    r.raise_for_status()
except HTTPError as e:
    print(f"HTTP Error: {e}")
except ConnectionError as e:
    print(f"Connection Error: {e}")
except Timeout as e:
    print(f"Timeout: {e}")
except RequestException as e:
    print(f"Request failed: {e}")
```

## API Reference

### Sync API

| Function | Description |
|----------|-------------|
| `requests.get(url, **kwargs)` | Send a GET request |
| `requests.post(url, **kwargs)` | Send a POST request |
| `requests.put(url, **kwargs)` | Send a PUT request |
| `requests.patch(url, **kwargs)` | Send a PATCH request |
| `requests.delete(url, **kwargs)` | Send a DELETE request |
| `requests.head(url, **kwargs)` | Send a HEAD request |
| `requests.options(url, **kwargs)` | Send an OPTIONS request |
| `requests.Session(...)` | Create a sync session |

### Async API

| Function | Description |
|----------|-------------|
| `await requests.async_get(url, **kwargs)` | Send an async GET request |
| `await requests.async_post(url, **kwargs)` | Send an async POST request |
| `await requests.async_put(url, **kwargs)` | Send an async PUT request |
| `await requests.async_patch(url, **kwargs)` | Send an async PATCH request |
| `await requests.async_delete(url, **kwargs)` | Send an async DELETE request |
| `await requests.async_head(url, **kwargs)` | Send an async HEAD request |
| `await requests.async_options(url, **kwargs)` | Send an async OPTIONS request |
| `requests.AsyncSession(...)` | Create an async session |

### Session Parameters

| Parameter | Description |
|-----------|-------------|
| `impersonate` | Browser to impersonate ('chrome', 'firefox', etc.) |
| `impersonate_os` | OS to impersonate ('windows', 'macos', 'linux', 'android', 'ios') |
| `base_url` | Base URL for relative request URLs |
| `params` | Default query parameters for all requests |
| `headers` | Default headers for all requests |
| `cookies` | Initial cookies |
| `auth` | HTTP basic auth tuple `(username, password)` |
| `proxy` | Single proxy URL for all requests |
| `proxies` | Dict of protocol-specific proxies |
| `proxy_auth` | Proxy authentication tuple `(username, password)` |
| `timeout` | Default timeout in seconds (or tuple for connect/read) |
| `verify` | Verify SSL certificates (default: True) |
| `allow_redirects` | Follow redirects (default: True) |
| `max_redirects` | Maximum redirects to follow (default: 30) |
| `retry` | Number of retries or `RetryStrategy` for failed requests |
| `raise_for_status` | Automatically raise HTTPError for 4xx/5xx (default: False) |
| `default_encoding` | Default encoding for response content (default: 'utf-8') |
| `default_headers` | Use default browser headers (default: True) |
| `discard_cookies` | Don't store cookies from responses (default: False) |
| `http_version` | HTTP version ('HTTP/1.1', 'HTTP/2', 'HTTP/3') |
| `interface` | Network interface to use |
| `cert` | Client certificate tuple `(cert_path, key_path)` |
| `debug` | Enable debug mode (default: False) |

### Request Parameters

| Parameter | Description |
|-----------|-------------|
| `params` | Query string parameters |
| `data` | Form data or request body |
| `json` | JSON data (auto-sets Content-Type) |
| `headers` | HTTP headers |
| `cookies` | Cookies to send |
| `files` | Files to upload (requests-style) |
| `multipart` | Multipart form data (curl_cffi-style) |
| `auth` | Basic auth tuple `(username, password)` |
| `timeout` | Request timeout in seconds |
| `allow_redirects` | Follow redirects (default: True) |
| `proxies` | Proxy configuration |
| `proxy_auth` | Proxy authentication tuple |
| `verify` | Verify SSL certificates |
| `referer` | Shortcut for setting Referer header |
| `default_encoding` | Override session default encoding |
| `discard_cookies` | Don't store cookies from this response |

## API Comparison

### requests compatibility

| requests | rnet-requests | Notes |
|----------|--------------|-------|
| `requests.get()` | `requests.get()` | ✅ Same |
| `requests.post()` | `requests.post()` | ✅ Same |
| `requests.Session()` | `requests.Session()` | ✅ Same + `impersonate` |
| - | `requests.AsyncSession()` | ✨ Async support |
| - | `requests.async_get()` | ✨ Async support |
| `r.json()` | `r.json()` | ✅ Same |
| `r.text` | `r.text` | ✅ Same |
| `r.content` | `r.content` | ✅ Same |
| `r.status_code` | `r.status_code` | ✅ Same |
| `r.headers` | `r.headers` | ✅ Same (CaseInsensitiveDict) |
| `r.cookies` | `r.cookies` | ✅ Dict instead of CookieJar |
| `r.raise_for_status()` | `r.raise_for_status()` | ✅ Same |

### curl_cffi compatibility

| curl_cffi | rnet-requests | Notes |
|-----------|--------------|-------|
| `Session(base_url=...)` | `Session(base_url=...)` | ✅ Same |
| `Session(params=...)` | `Session(params=...)` | ✅ Same |
| `Session(proxy=...)` | `Session(proxy=...)` | ✅ Same |
| `Session(cookies=...)` | `Session(cookies=...)` | ✅ Same |
| `Session(impersonate=...)` | `Session(impersonate=...)` | ✅ Same |
| `Session(retry=...)` | `Session(retry=...)` | ✅ Same (with `RetryStrategy`) |
| `Session(raise_for_status=...)` | `Session(raise_for_status=...)` | ✅ Same |
| `Session(default_encoding=...)` | `Session(default_encoding=...)` | ✅ Same |
| `Session(discard_cookies=...)` | `Session(discard_cookies=...)` | ✅ Same |
| `Session(http_version=...)` | `Session(http_version=...)` | ✅ Same |
| `request(referer=...)` | `request(referer=...)` | ✅ Same |
| `Headers` class | `Headers` class | ✅ Same (with `get_list()`) |
| `Cookies` class | `Cookies` class | ✅ Same (with domain support) |
| `request(multipart=...)` | `request(multipart=...)` | ✅ Same |
| `Multipart.from_list()` | `Multipart.from_list()` | ✅ Same |
| `session.ws_connect()` | `session.ws_connect()` | ✅ Async only |
| `response.history` | `response.history` | ✅ Same |
| `response.elapsed` | `response.elapsed` | ✅ Same |
| `Session(extra_fp=...)` | Use `TlsOptions`/`Http2Options` | ⚠️ See note below |
| `Session(ja3=...)` | Not supported | ❌ Use `impersonate` instead |
| `Session(akamai=...)` | Not supported | ❌ Use `impersonate` instead |

#### Note on `extra_fp`, `ja3`, and `akamai` parameters

curl_cffi's `extra_fp` parameter allows fine-grained control over TLS/HTTP2 fingerprints:

```python
# curl_cffi - fine-grained TLS/HTTP2 control
from curl_cffi.requests import Session
Session(extra_fp={
    "tls_grease": True,
    "tls_permute_extensions": True,
    "http2_stream_weight": 256,
})
```

rnet handles fingerprinting differently - the `impersonate` parameter selects a complete browser profile that includes all TLS/HTTP2 settings. For most use cases, this is sufficient and simpler:

```python
# rnet-requests - browser-based impersonation
from rnet_requests import Session
Session(impersonate='chrome', impersonate_os='windows')
```

If you need low-level TLS/HTTP2 control, rnet does expose `TlsOptions` and `Http2Options` which can be passed directly to the rnet `Client`, but this is not wrapped by rnet-requests as it's rarely needed.

Similarly, curl_cffi's `ja3` and `akamai` string parameters for custom fingerprints are not supported - use `impersonate` with a browser name instead.

## Migration from requests

In most cases, you can simply change your import:

```python
# Before
import requests

# After
import rnet_requests as requests
```

That's it! Your existing code should work with rnet-requests.

For async code, use the async variants:

```python
# Sync
r = requests.get(url)

# Async
r = await requests.async_get(url)

# Or with sessions
async with requests.AsyncSession() as s:
    r = await s.get(url)
```

## Migration from curl_cffi

```python
# Before
from curl_cffi.requests import Session

# After
from rnet_requests import Session

# Most curl_cffi patterns work directly:
with Session(base_url='https://api.example.com', impersonate='chrome') as s:
    r = s.get('/endpoint')
```

## Requirements

- Python 3.11+
- rnet >= 3.0.0

## License

MIT License

## Credits

- [rnet](https://github.com/0x676e67/rnet) - The underlying HTTP client
- [requests](https://github.com/psf/requests) - API design inspiration
- [curl_cffi](https://github.com/yifeikong/curl_cffi) - curl_cffi API patterns
