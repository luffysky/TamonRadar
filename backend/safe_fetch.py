"""對外抓取使用者提供的網址時的集中防護(SSRF)。

- validate_url:只允許 http/https,DNS 解析後所有 IP 都必須是公網。
- safe_get:自己處理轉址、每一跳都重新驗證,並限制回應大小與總時間。
- 連線當下再解析一次並「釘住」驗證過的 IP,避免 DNS rebinding(驗證時公網、連線時內網)。
"""
import ipaddress
import os
import socket
import time
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError
from urllib3.util import connection as _u3_connection

MAX_URL_LENGTH = 1000
DEFAULT_MAX_BYTES = int(os.environ.get("FETCH_MAX_BYTES", str(8 * 1024 * 1024)))
MAX_REDIRECTS = 5
_REDIRECT_CODES = (301, 302, 303, 307, 308)

_NAT64 = ipaddress.ip_network("64:ff9b::/96")
# is_global 判斷不到、但實際上是雲端內部服務的位址(Azure wireserver)
_EXTRA_BLOCKED = {ipaddress.ip_address("168.63.129.16")}


class UnsafeURLError(ValueError):
    """網址不允許抓取。訊息可直接顯示給使用者(不含解析出的 IP)。"""


class ResponseTooLarge(Exception):
    """回應超過大小上限,或下載超過總時間。"""


def _ip_is_public(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text.split("%", 1)[0])
    if ip.version == 6:
        if ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        elif ip.sixtofour:
            ip = ip.sixtofour
        elif ip.teredo:
            return False
        elif ip in _NAT64:
            ip = ipaddress.ip_address(int(ip) & 0xFFFFFFFF)
    if ip in _EXTRA_BLOCKED:
        return False
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_loopback
                                 or ip.is_link_local or ip.is_unspecified or ip.is_private)


def _resolve(host: str, port: int) -> list[str]:
    """回傳該主機解析出的所有 IP;任何一個不是公網就整個拒絕。"""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError):
        raise UnsafeURLError("網址無法解析,請確認網址是否正確")
    ips = list(dict.fromkeys(info[4][0] for info in infos))
    if not ips or not all(_ip_is_public(ip) for ip in ips):
        raise UnsafeURLError("不允許抓取內部或保留網段的網址")
    return ips


def validate_url(url: str, resolve: bool = True) -> str:
    """檢查網址是否可抓取並回傳清理後的網址。resolve=False 時只做語法與 IP 字面值檢查(不查 DNS)。"""
    url = (url or "").strip()
    if not url or len(url) > MAX_URL_LENGTH:
        raise UnsafeURLError("網址不正確或太長")
    if any(c in url for c in "\\\r\n\t") or any(ord(c) < 0x20 for c in url):
        raise UnsafeURLError("網址含有不允許的字元")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise UnsafeURLError("網址格式不正確")
    if parts.scheme.lower() not in ("http", "https"):
        raise UnsafeURLError("只支援 http / https 網址")
    if not host:
        raise UnsafeURLError("網址格式不正確")
    if parts.username is not None or parts.password is not None:
        raise UnsafeURLError("網址不可包含帳號密碼")
    port = port or (443 if parts.scheme.lower() == "https" else 80)
    if resolve:
        _resolve(host, port)
        return url
    lowered = host.lower().rstrip(".")
    if lowered == "localhost" or lowered.endswith((".localhost", ".local", ".internal")):
        raise UnsafeURLError("不允許抓取內部或保留網段的網址")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        return url  # 一般網域名稱:實際抓取時才會解析檢查
    if not _ip_is_public(str(literal)):
        raise UnsafeURLError("不允許抓取內部或保留網段的網址")
    return url


# ---------- 連線層:連線當下重新驗證並釘住 IP ----------

class _SafeConnectMixin:
    def _new_conn(self):
        ips = _resolve(self._dns_host, self.port)
        last_error: OSError | None = None
        for ip in ips:
            try:
                return _u3_connection.create_connection(
                    (ip, self.port), self.timeout,
                    source_address=self.source_address, socket_options=self.socket_options,
                )
            except socket.timeout as e:
                raise ConnectTimeoutError(self, f"連線逾時:{self.host}") from e
            except OSError as e:
                last_error = e
        raise NewConnectionError(self, f"無法連線:{last_error}")


class _SafeHTTPConnection(_SafeConnectMixin, HTTPConnection):
    pass


class _SafeHTTPSConnection(_SafeConnectMixin, HTTPSConnection):
    pass


class _SafeHTTPPool(HTTPConnectionPool):
    ConnectionCls = _SafeHTTPConnection


class _SafeHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _SafeHTTPSConnection


class _SafeAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)
        self.poolmanager.pool_classes_by_scheme = {"http": _SafeHTTPPool, "https": _SafeHTTPSPool}


def _new_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False  # 不走環境變數代理,否則連線層的 IP 檢查會被繞過
    adapter = _SafeAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _open(session: requests.Session, url: str, headers: dict | None, timeout: float) -> requests.Response:
    return session.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=False)


def _read_limited(resp: requests.Response, max_bytes: int, deadline: float) -> None:
    """邊下載邊檢查大小與總時間,讀完後 resp.text / resp.json() 可照常使用。"""
    declared = resp.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        resp.close()
        raise ResponseTooLarge("回應內容太大,已停止下載")
    chunks: list[bytes] = []
    total = 0
    for chunk in resp.iter_content(64 * 1024):
        total += len(chunk)
        if total > max_bytes:
            resp.close()
            raise ResponseTooLarge("回應內容太大,已停止下載")
        if time.monotonic() > deadline:
            resp.close()
            raise ResponseTooLarge("下載時間過長,已停止")
        chunks.append(chunk)
    resp._content = b"".join(chunks)
    resp._content_consumed = True


def safe_get(url: str, headers: dict | None = None, timeout: float = 15,
             max_bytes: int = DEFAULT_MAX_BYTES, max_redirects: int = MAX_REDIRECTS) -> requests.Response:
    """安全版 requests.get。網址不合規丟 UnsafeURLError,太大丟 ResponseTooLarge,網路錯誤照 requests 例外。"""
    deadline = time.monotonic() + max(timeout * 3, 30)
    current = validate_url(url)
    session = _new_session()
    try:
        for _ in range(max_redirects + 1):
            resp = _open(session, current, headers, timeout)
            location = resp.headers.get("location")
            if resp.status_code in _REDIRECT_CODES and location:
                resp.close()
                current = validate_url(urljoin(current, location))  # 每一跳都重新驗證
                continue
            _read_limited(resp, max_bytes, deadline)
            return resp
        raise UnsafeURLError("重新導向次數過多")
    finally:
        session.close()
