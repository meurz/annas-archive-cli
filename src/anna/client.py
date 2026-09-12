import hashlib
import http.cookiejar
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from anna.errors import AnnaError
from anna.parsing import Book, document, parse_info, parse_search, record_id, text

DEFAULT_BASE_URL = "https://annas-archive.gl"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def http_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
        )
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise AnnaError("地址必须是有效 HTTP(S) URL，且不能在 URL 中包含用户名或密码。")
    return value


def safe_filename(name: str) -> str:
    name = unquote(name).replace("\\", "/").split("/")[-1]
    name = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', "_", name).strip(" .")
    # Bound UTF-8 bytes to leave room for the temporary filename suffix.
    while len(name.encode("utf-8")) > 180:
        name = name[:-1]
    return name or "download.bin"


def response_filename(response: httpx.Response) -> str:
    disposition = response.headers.get("content-disposition", "")
    encoded = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I)
    ordinary = re.search(r'filename="([^"]+)"|filename=([^;]+)', disposition, re.I)
    if encoded:
        return safe_filename(encoded[1])
    if ordinary:
        return safe_filename(ordinary[1] or ordinary[2])
    return safe_filename(urlsplit(str(response.url)).path.rsplit("/", 1)[-1])


def check_status(response: httpx.Response) -> None:
    if response.status_code == 429:
        retry = response.headers.get("retry-after", "")
        suffix = f"（Retry-After: {retry}）" if retry else ""
        raise AnnaError(f"站点限流，请稍后重试{suffix}。")
    if response.status_code >= 400:
        if response.status_code in {401, 403, 503}:
            # Inspect a bounded body; challenge responses may use an error status.
            document(response.text[:1_000_000])
        raise AnnaError(f"服务器返回 HTTP {response.status_code}，请检查镜像、记录或访问权限。")


class Client:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30,
        cookies: Path | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = http_url(base_url).rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.path or parsed.query or parsed.fragment:
            raise AnnaError("--base-url 只接受站点根地址，例如 https://annas-archive.gl。")
        jar = http.cookiejar.MozillaCookieJar()
        if cookies:
            try:
                jar.load(str(cookies), ignore_discard=True, ignore_expires=True)
                # Browser exporters commonly encode session expiry as 0;
                # MozillaCookieJar otherwise treats it as January 1970.
                for cookie in jar:
                    if cookie.expires == 0:
                        cookie.expires = None
                        cookie.discard = True
                jar.clear_expired_cookies()
            except (OSError, http.cookiejar.LoadError) as exc:
                raise AnnaError("无法读取 Cookie 文件，请使用 Netscape cookies.txt 格式。") from exc
        self.http = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=10,
            headers={"User-Agent": user_agent, "Accept-Language": "en-US,en;q=0.9"},
            cookies=jar,
            transport=transport,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.http.close()

    def page(self, path: str, params: dict | None = None) -> httpx.Response:
        response = self.http.get(self.base_url + path, params=params)
        check_status(response)
        return response

    def search(self, query: str, **filters) -> list[Book]:
        if not query.strip():
            raise AnnaError("搜索词不能为空。")
        params = {"q": query, "display": "", **{k: v for k, v in filters.items() if v}}
        response = self.page("/search", params)
        return parse_search(response.text, str(response.url))

    def info(self, value: str) -> Book:
        md5 = record_id(value)
        response = self.page(f"/md5/{md5}")
        return parse_info(response.text, str(response.url), md5)

    def download(
        self,
        url: str,
        output: Path | None = None,
        directory: Path = Path("."),
        expected_md5: str | None = None,
    ) -> dict:
        if expected_md5:
            expected_md5 = record_id(expected_md5)
        for _ in range(4):
            http_url(url)
            with self.http.stream("GET", url) as response:
                if response.status_code >= 400:
                    check_status(
                        httpx.Response(
                            response.status_code,
                            headers=response.headers,
                            content=self._read_page(response),
                            request=response.request,
                        )
                    )
                if response.status_code != 200:
                    raise AnnaError(f"下载需要完整文件，服务器返回 HTTP {response.status_code}。")
                chunks = response.iter_bytes(chunk_size=65536)
                first = next(chunks, b"")
                content_type = response.headers.get("content-type", "").lower()
                prefix = first.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
                is_html = "html" in content_type or prefix.startswith(
                    (b"<!doctype html", b"<html", b"<head", b"<script", b"<body")
                )
                if is_html:
                    body = bytearray(first)
                    for chunk in chunks:
                        body.extend(chunk)
                        if len(body) > 2_000_000:
                            raise AnnaError("下载入口返回过大的 HTML 页面，未保存为文件。")
                    soup = document(body.decode("utf-8", errors="replace"))
                    # Only follow explicit file download controls, never arbitrary links/JS.
                    candidates = soup.select("a[download][href], a#download[href]")
                    if not candidates:
                        candidates = [
                            a
                            for a in soup.select("a[href]")
                            if text(a).lower()
                            in {"get", "download now", "download file", "立即下载"}
                        ]
                    target = next(
                        (
                            urljoin(str(response.url), a["href"])
                            for a in candidates
                            if urljoin(str(response.url), a["href"]) != str(response.url)
                        ),
                        None,
                    )
                    if not target:
                        raise AnnaError(
                            "下载入口返回网页，可能需要浏览器验证、登录或等待。"
                            "请在浏览器取得最终文件 URL 后执行 anna download URL；未保存网页。"
                        )
                    url = target
                    continue
                if ("json" in content_type or prefix.startswith((b'{"', b"{\n"))) or (
                    "xml" in content_type or prefix.startswith(b"<?xml")
                ):
                    raise AnnaError("下载入口返回 JSON/XML 响应，未保存为电子书。")
                if not first:
                    raise AnnaError("服务器返回空文件，下载已取消。")
                destination = output or directory / response_filename(response)
                if destination.exists() or destination.is_symlink():
                    raise AnnaError(f"文件已存在，不会覆盖：{destination}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(
                    prefix=".anna-", suffix=".part", dir=destination.parent
                )
                digest = hashlib.md5(usedforsecurity=False)
                size = 0
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(first)
                        digest.update(first)
                        size += len(first)
                        for chunk in chunks:
                            stream.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                        stream.flush()
                        os.fsync(stream.fileno())
                    declared = response.headers.get("content-length")
                    if declared and not response.headers.get("content-encoding"):
                        if not declared.isdigit():
                            raise AnnaError("服务器返回无效 Content-Length，下载已取消。")
                        if int(declared) != size:
                            raise AnnaError("下载大小与 Content-Length 不符，未保留损坏文件。")
                    checksum = digest.hexdigest()
                    if expected_md5 and checksum != expected_md5:
                        raise AnnaError("文件 MD5 校验失败，未保留损坏文件。")
                    # Atomic publication with no overwrite, including concurrent invocations.
                    os.link(temporary, destination)
                finally:
                    Path(temporary).unlink(missing_ok=True)
                return {"path": str(destination.resolve()), "bytes": size, "md5": checksum}
        raise AnnaError("下载入口跳转层数过多，请提供最终文件 URL。")

    @staticmethod
    def _read_page(response: httpx.Response) -> bytes:
        body = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            body.extend(chunk)
            if len(body) > 2_000_000:
                raise AnnaError(f"服务器返回 HTTP {response.status_code}。")
        return bytes(body)
