"""HTML adapters for the public list and record pages; no JavaScript execution."""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Comment, Tag

from anna.errors import AnnaError, ChallengeError, ParseError

MD5 = re.compile(r"^[0-9a-fA-F]{32}$")
MD5_PATH = re.compile(r"^/md5/([0-9a-fA-F]{32})/?$")


@dataclass
class Link:
    label: str
    url: str
    kind: str


@dataclass
class Book:
    md5: str
    title: str
    url: str
    author: str = ""
    publisher: str = ""
    language: str = ""
    format: str = ""
    size: str = ""
    metadata: str = ""
    cover_url: str = ""
    description: str = ""
    links: list[Link] = field(default_factory=list)


def record_id(value: str) -> str:
    value = value.strip()
    if MD5.fullmatch(value):
        return value.lower()
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise AnnaError("详情链接格式无效。") from exc
    match = MD5_PATH.fullmatch(parsed.path)
    if match and (not parsed.scheme or parsed.scheme in {"http", "https"}):
        return match[1].lower()
    raise AnnaError("请输入 32 位 MD5 或 /md5/<MD5> 书籍详情链接。")


def text(node: Tag | None) -> str:
    if node is None:
        return ""
    # Search icons, script text and hidden ranking metadata are not book titles.
    clone = BeautifulSoup(str(node), "html.parser")
    for child in clone.select(".select-none, script, style, .hidden"):
        child.decompose()
    return " ".join(clone.stripped_strings)


def document(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    title = text(soup.title).lower()
    challenge = (
        any(s in title for s in ("ddos-guard", "just a moment", "attention required"))
        or soup.select_one('script[src*="ddos-guard"], script[src*="challenge-platform"]')
        or soup.select_one("#challenge-form, #cf-challenge-running")
    )
    if challenge:
        raise ChallengeError(
            "站点要求浏览器验证。请在浏览器打开该镜像完成验证，导出 Netscape Cookie "
            "文件后使用 --cookies；Cookie 可能绑定 IP 和 User-Agent，"
            "也可用 --base-url 切换镜像。CLI 不执行验证脚本。"
        )
    if any(s in html.lower() for s in ("this domain may be for sale", "forsale.min.js")):
        raise ParseError("该域名是停放页，请用 --base-url 指定已确认的 Anna’s Archive 镜像。")
    # The site progressively reveals result cards stored inside HTML comments.
    for container in soup.select(".js-scroll-hidden"):
        for comment in list(container.find_all(string=lambda x: isinstance(x, Comment))):
            fragment = BeautifulSoup(str(comment), "html.parser")
            comment.replace_with(fragment)
    return soup


def metadata_fields(value: str) -> dict[str, str]:
    parts = [p.strip() for p in value.split(",")]
    language = re.search(r"\[([a-z]{2,3}(?:[-_][\w]+)?)\]", value, re.I)
    extension = next(
        (
            p.lower()
            for p in parts
            if re.fullmatch(r"pdf|epub|mobi|azw3?|djvu?|txt|rtf|docx?|cb[rz]|fb2|zip|html", p, re.I)
        ),
        "",
    )
    size = re.search(r"\b\d+(?:[.,]\d+)?\s*[KMGT]?i?B\b", value, re.I)
    return {
        "metadata": value,
        "language": language[1] if language else "",
        "format": extension,
        "size": size[0] if size else "",
    }


def parse_search(html: str, base_url: str) -> list[Book]:
    soup = document(html)
    books: dict[str, Book] = {}
    for anchor in soup.select('a[href*="/md5/"]'):
        match = MD5_PATH.fullmatch(urlsplit(anchor.get("href", "")).path)
        if not match:
            continue
        md5 = match[1].lower()
        if md5 in books:
            continue
        title = anchor.select_one("h3") or anchor.select_one(".font-bold")
        if title is None:
            continue  # Cover-only anchors and unrelated links are not results.
        meta = anchor.select_one(".text-gray-500")
        author = anchor.select_one(".italic")
        publisher = title.find_next_sibling("div")
        cover = anchor.select_one("img[src]")
        books[md5] = Book(
            md5=md5,
            title=text(title),
            url=urljoin(base_url, f"/md5/{md5}"),
            author=text(author),
            publisher=text(publisher) if publisher != author else "",
            cover_url=urljoin(base_url, cover["src"]) if cover else "",
            **metadata_fields(text(meta)),
        )
    if not books:
        visible = soup.get_text(" ", strip=True).lower()
        if not any(
            s in visible
            for s in (
                "no files found",
                "no results found",
                "no results",
                "没有找到",
                "未找到",
                "找不到",
            )
        ):
            raise ParseError("未识别到搜索结果结构（可能是验证页或站点改版），未将其当作空结果。")
    return list(books.values())


def extract_links(soup: BeautifulSoup, base_url: str) -> list[Link]:
    links = []
    seen = set()
    for anchor in soup.select("a.js-download-link[href]"):
        url = urljoin(base_url, anchor["href"])
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "http", "magnet", "ipfs"} or url in seen:
            continue
        seen.add(url)
        path = parsed.path
        kind = (
            "fast"
            if "/fast_download/" in path
            else ("slow" if "/slow_download/" in path else "external")
        )
        links.append(Link(text(anchor) or parsed.hostname or kind, url, kind))
    return links


def parse_info(html: str, base_url: str, md5: str) -> Book:
    soup = document(html)
    title = soup.select_one(".text-3xl")
    if title is None:
        raise ParseError("未识别到书籍详情结构（记录不存在、验证页或站点改版）。")
    meta = title.find_previous_sibling("div")
    publisher = title.find_next_sibling("div")
    author = publisher.find_next_sibling("div") if publisher else None
    cover = soup.select_one(".js-cover-background")
    cover = cover.parent.select_one("img[src]") if cover else None
    return Book(
        md5=md5,
        title=text(title),
        url=urljoin(base_url, f"/md5/{md5}"),
        author=text(author),
        publisher=text(publisher),
        cover_url=urljoin(base_url, cover["src"]) if cover else "",
        description=text(soup.select_one(".js-md5-top-box-description")),
        links=extract_links(soup, base_url),
        **metadata_fields(text(meta)),
    )
