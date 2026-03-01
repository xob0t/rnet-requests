# rnet-requests

Drop-in replacement for `requests` and `curl_cffi` using [rnet](https://github.com/0x676e67/rnet) as the backend.

rnet is a Rust-based HTTP client with TLS fingerprint impersonation. This wrapper gives you a familiar Python API.

## Install

```bash
pip install git+https://github.com/user/rnet-requests.git
```

Or clone and install locally:

```bash
git clone https://github.com/user/rnet-requests.git
cd rnet-requests
pip install -e .
```

## Usage

```python
import rnet_requests as requests

# Works like requests
r = requests.get('https://httpbin.org/get')
print(r.json())

# With browser impersonation
r = requests.get('https://httpbin.org/get', impersonate='chrome')

# Sessions
with requests.Session(impersonate='chrome') as s:
    s.get('https://httpbin.org/cookies/set/foo/bar')
    r = s.get('https://httpbin.org/cookies')
    print(r.json())  # {'cookies': {'foo': 'bar'}}
```

### Async

```python
import asyncio
import rnet_requests as requests

async def main():
    r = await requests.async_get('https://httpbin.org/get')
    print(r.json())

    async with requests.AsyncSession(impersonate='firefox') as s:
        r = await s.get('https://httpbin.org/get')

asyncio.run(main())
```

### Impersonation

The main reason to use this library - bypass TLS fingerprinting:

```python
import rnet_requests as requests

# Simple: just pass a browser name
r = requests.get('https://tls.peet.ws/api/all', impersonate='chrome')

# With OS fingerprint
with requests.Session(impersonate='chrome', impersonate_os='windows') as s:
    r = s.get('https://tls.peet.ws/api/all')
    print(r.json()['tls']['ja3_hash'])

# Specific version
with requests.Session(impersonate='chrome136') as s:
    r = s.get('https://tls.peet.ws/api/all')
```

**Available browsers:**
- `chrome` (or specific: `chrome136`, `chrome140`, etc.)
- `firefox` (or specific: `firefox139`, `firefox147`, etc.)
- `safari` (or specific: `safari18`, `safariios18_1_1`, etc.)
- `edge` (or specific: `edge145`, etc.)
- `opera` (or specific: `opera119`, etc.)
- `okhttp` (or specific: `okhttp5`, `okhttp4_12`, etc.)

**Available OS:**
- `windows`, `macos`, `linux`, `android`, `ios`

You can also use rnet's native types directly:

```python
from rnet import Emulation, EmulationOS, EmulationOption

with requests.Session(
    impersonate=EmulationOption(Emulation.Chrome140, emulation_os=EmulationOS.Windows)
) as s:
    r = s.get('https://httpbin.org/get')
```

### Streaming

```python
with requests.Session() as s:
    r = s.get('https://httpbin.org/stream/10', stream=True)
    for line in r.iter_lines():
        print(line)

# Async streaming
async with requests.AsyncSession() as s:
    r = await s.get('https://httpbin.org/stream/10', stream=True)
    async for line in r.aiter_lines():
        print(line)
```

### WebSockets

```python
async with requests.AsyncSession() as s:
    async with s.ws_connect('wss://echo.websocket.org') as ws:
        await ws.send_str('hello')
        msg = await ws.recv_str()
```

## curl_cffi Features

Most curl_cffi patterns work:

```python
from rnet_requests import Session, Headers, Cookies, Multipart

# base_url
with Session(base_url='https://api.example.com/v1') as s:
    r = s.get('/users')  # https://api.example.com/v1/users

# default params
with Session(params={'api_key': 'secret'}) as s:
    r = s.get('https://api.example.com/data')

# proxy
with Session(proxy='http://localhost:8080') as s:
    r = s.get('https://httpbin.org/ip')

# retry
from rnet_requests import RetryStrategy
with Session(retry=RetryStrategy(count=3, backoff='exponential')) as s:
    r = s.get('https://httpbin.org/get')

# multipart uploads
mp = Multipart()
mp.addpart('file', filename='data.csv', data=b'a,b,c\n1,2,3')
with Session() as s:
    r = s.post('https://httpbin.org/post', multipart=mp)
```

## Session Options

| Parameter          | Description                                                              |
| ------------------ | ------------------------------------------------------------------------ |
| `impersonate`      | Browser to impersonate (`'chrome'`, `'firefox'`, etc.)                   |
| `impersonate_os`   | OS fingerprint (`'windows'`, `'macos'`, `'linux'`, `'android'`, `'ios'`) |
| `base_url`         | Prepended to relative URLs                                               |
| `params`           | Default query params                                                     |
| `headers`          | Default headers                                                          |
| `cookies`          | Initial cookies                                                          |
| `proxy`            | Proxy URL                                                                |
| `timeout`          | Request timeout (seconds)                                                |
| `verify`           | Verify SSL (default: `True`)                                             |
| `retry`            | Retry count or `RetryStrategy`                                           |
| `raise_for_status` | Auto-raise on 4xx/5xx                                                    |

## Request Options

| Parameter   | Description                      |
| ----------- | -------------------------------- |
| `params`    | Query string params              |
| `data`      | Form data / body                 |
| `json`      | JSON body                        |
| `headers`   | Request headers                  |
| `cookies`   | Request cookies                  |
| `files`     | File uploads (requests-style)    |
| `multipart` | Multipart form (curl_cffi-style) |
| `auth`      | Basic auth `(user, pass)`        |
| `timeout`   | Timeout in seconds               |
| `stream`    | Stream response body             |
| `referer`   | Referer header shortcut          |

## Response

```python
r.status_code   # 200
r.ok            # True
r.text          # decoded string
r.content       # bytes
r.json()        # parsed JSON
r.headers       # case-insensitive dict
r.cookies       # cookies
r.url           # final URL after redirects
r.elapsed       # request duration
r.history       # redirect history
```

## Exceptions

```python
from rnet_requests import RequestException, ConnectionError, Timeout, HTTPError

try:
    r = requests.get('https://httpbin.org/status/500')
    r.raise_for_status()
except HTTPError as e:
    print(e)
```

## Migration

From requests:

```python
# import requests
import rnet_requests as requests
```

From curl_cffi:

```python
# from curl_cffi.requests import Session
from rnet_requests import Session
```

## Not Supported

- `ja3` / `akamai` string parameters (use `impersonate` instead)
- `extra_fp` for manual fingerprint tuning (rnet handles this via browser profiles)

## Requirements

- Python 3.11+
- rnet

## License

MIT
