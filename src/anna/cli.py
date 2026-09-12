import json
from dataclasses import asdict
from pathlib import Path

import click
import httpx

from anna import __version__
from anna.client import DEFAULT_BASE_URL, DEFAULT_USER_AGENT, Client
from anna.errors import AnnaError
from anna.parsing import record_id


class ErrorGroup(click.Group):
    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except (AnnaError, httpx.HTTPError, OSError) as exc:
            if isinstance(exc, httpx.HTTPError):
                message = f"网络请求失败（{type(exc).__name__}），请检查网络、代理或 --base-url。"
            elif isinstance(exc, OSError):
                message = f"文件操作失败：{exc.strerror or type(exc).__name__}。"
            else:
                message = str(exc)
            if (ctx.obj or {}).get("json"):
                click.echo(
                    json.dumps(
                        {"error": {"type": type(exc).__name__, "message": message}},
                        ensure_ascii=False,
                    )
                )
                ctx.exit(1)
            raise click.ClickException(message) from exc


@click.group(cls=ErrorGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--base-url",
    envvar="ANNA_BASE_URL",
    default=DEFAULT_BASE_URL,
    show_default=True,
    help="镜像根地址。",
)
@click.option(
    "--cookies",
    envvar="ANNA_COOKIES",
    type=click.Path(path_type=Path, exists=True),
    help="浏览器导出的 Netscape Cookie 文件。",
)
@click.option(
    "--user-agent",
    envvar="ANNA_USER_AGENT",
    default=DEFAULT_USER_AGENT,
    help="使用 Cookie 时可设为浏览器的 User-Agent。",
)
@click.option(
    "--timeout",
    envvar="ANNA_TIMEOUT",
    type=click.FloatRange(min=0, min_open=True),
    default=30,
    show_default=True,
    help="网络超时秒数。",
)
@click.option("--json", "json_output", is_flag=True, help="输出 JSON。子命令后也可使用。")
@click.version_option(__version__)
@click.pass_context
def main(ctx, base_url, cookies, user_agent, timeout, json_output):
    """搜索 Anna’s Archive、查看书籍、获取链接和下载文件。"""
    ctx.ensure_object(dict)
    ctx.obj.update(
        json=json_output,
        client_options=dict(
            base_url=base_url, cookies=cookies, user_agent=user_agent, timeout=timeout
        ),
    )


def json_option(function):
    return click.option("--json", "json_output", is_flag=True, help="输出 JSON。")(function)


def prepare(ctx, json_output):
    ctx.obj["json"] = ctx.obj["json"] or json_output
    return Client(**ctx.obj["client_options"])


def emit(value):
    click.echo(json.dumps(value, ensure_ascii=False, indent=2))


@main.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--lang", multiple=True, help="语言代码，可重复：zh、en、ja。")
@click.option("--ext", multiple=True, help="文件格式，可重复：epub、pdf。")
@click.option("--content", multiple=True, help="内容类型，如 book_nonfiction、book_fiction。")
@click.option(
    "--sort",
    type=click.Choice(
        ["relevance", "newest", "oldest", "largest", "smallest", "newest_added", "oldest_added"]
    ),
    default="relevance",
    show_default=True,
)
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=20,
    show_default=True,
    help="本页最多输出多少条，不会自动翻页。",
)
@json_option
@click.pass_context
def search(ctx, query, lang, ext, content, sort, page, limit, json_output):
    """按标题、作者、ISBN 或关键词搜索。"""
    with prepare(ctx, json_output) as client:
        books = client.search(
            " ".join(query),
            lang=lang,
            ext=ext,
            content=content,
            sort="" if sort == "relevance" else sort,
            page=page,
        )[:limit]
    if ctx.obj["json"]:
        emit([asdict(book) for book in books])
    elif not books:
        click.echo("没有找到匹配书籍。")
    else:
        for i, book in enumerate(books, 1):
            click.echo(f"{i}. {book.title}")
            click.echo(f"   {book.author or '作者未知'} | {book.metadata}")
            click.echo(f"   {book.url}")


@main.command()
@click.argument("record")
@json_option
@click.pass_context
def info(ctx, record, json_output):
    """查看书籍详情，接受 MD5 或详情 URL。"""
    with prepare(ctx, json_output) as client:
        book = client.info(record)
    if ctx.obj["json"]:
        emit(asdict(book))
    else:
        for label, value in [
            ("书名", book.title),
            ("作者", book.author),
            ("出版", book.publisher),
            ("文件", book.metadata),
            ("MD5", book.md5),
            ("链接", book.url),
            ("简介", book.description),
        ]:
            if value:
                click.echo(f"{label}：{value}")
        click.echo(f"下载入口：{len(book.links)} 个（anna links {book.md5}）")


@main.command()
@click.argument("record")
@json_option
@click.pass_context
def links(ctx, record, json_output):
    """列出详情页中的下载入口（入口可能仍需验证或登录）。"""
    with prepare(ctx, json_output) as client:
        book = client.info(record)
    if ctx.obj["json"]:
        emit([{"index": i, **asdict(link)} for i, link in enumerate(book.links, 1)])
    else:
        for i, link in enumerate(book.links, 1):
            click.echo(f"{i}. [{link.kind}] {link.label}\n   {link.url}")
        if not book.links:
            click.echo("该记录没有可用下载入口。")


@main.command()
@click.argument("target")
@click.option("--source", type=click.IntRange(min=1), help="anna links 显示的入口编号。")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="保存文件路径。不会覆盖。")
@click.option(
    "-d",
    "--directory",
    type=click.Path(path_type=Path),
    default=".",
    help="未指定 -o 时的保存目录。",
)
@click.option("--md5", "expected_md5", help="下载直接 URL 时额外校验文件 MD5。")
@json_option
@click.pass_context
def download(ctx, target, source, output, directory, expected_md5, json_output):
    """下载 MD5/详情链接对应的文件，或指定的 HTTP(S) 文件 URL。"""
    with prepare(ctx, json_output) as client:
        try:
            md5 = record_id(target)
        except AnnaError:
            md5 = None
        if md5:
            if expected_md5 and record_id(expected_md5) != md5:
                raise AnnaError("--md5 与书籍记录 MD5 不一致。")
            book = client.info(md5)
            if source:
                if source > len(book.links):
                    raise AnnaError(f"该记录只有 {len(book.links)} 个入口，--source 超出范围。")
                link = book.links[source - 1]
            else:
                link = next(
                    (
                        x
                        for x in book.links
                        if x.kind != "fast" and x.url.startswith(("http://", "https://"))
                    ),
                    None,
                )
            if not link:
                raise AnnaError("没有普通 HTTP 下载入口；请运行 anna links 检查可用来源。")
            target, expected_md5 = link.url, md5
        elif source:
            raise AnnaError("--source 仅用于 MD5 或书籍详情链接。")
        result = client.download(target, output, directory, expected_md5)
    if ctx.obj["json"]:
        emit(result)
    else:
        click.echo(f"已保存：{result['path']}\n大小：{result['bytes']} 字节\nMD5：{result['md5']}")


@main.command()
@json_option
@click.pass_context
def doctor(ctx, json_output):
    """检查当前镜像能否返回可解析的搜索结果。"""
    with prepare(ctx, json_output) as client:
        books = client.search("Pride and Prejudice", page=1)
        result = {"base_url": client.base_url, "ok": True, "results": len(books)}
    if ctx.obj["json"]:
        emit(result)
    else:
        click.echo(f"镜像可访问并成功解析：{result['base_url']}（{result['results']} 条）")
