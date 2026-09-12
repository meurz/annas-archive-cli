# Anna’s Archive CLI

终端中搜索书籍、查看详情、列出下载入口，以及下载文件。命令名 `anna`，Python 3.11+。

## 安装

```bash
uv tool install .
anna --help
```

也可使用 `pipx install .`，或开发环境 `uv sync --group dev` 后运行 `uv run anna`。

## 使用

```bash
anna search 三体 --lang zh --ext epub
anna search "Jane Austen" --ext epub --ext pdf --sort smallest --limit 5
anna search "Pride and Prejudice" --page 2 --json
```

搜索输出包含书籍详情 URL。将它或其中的 32 位 MD5 传给以下命令：

```bash
anna info "$BOOK_URL"
anna links "$BOOK_URL" --json
anna download "$BOOK_URL" --source 2 -o ./book.epub
anna download "$FILE_URL" -d ./downloads
anna download "$FILE_URL" --md5 "$EXPECTED_MD5" --json
```

`BOOK_URL` 是 `anna search` 返回的详情链接，`FILE_URL` 是最终 HTTP(S) 文件地址。
`--source` 对应 `anna links` 中从 1 开始的编号；省略时选择第一个非 fast 的 HTTP 入口。
`--limit` 限制当前页输出条数，`--page` 请求指定页，不自动批量翻页。

下载会跟随 HTTP 重定向和明确的文件下载按钮，流式写入同目录临时文件，完成后原子发布。
从 MD5/详情 URL 发起时强制校验 MD5；直接 URL 可通过 `--md5` 指定校验值。
默认不覆盖已有文件，失败清理临时文件；拒绝 HTML 验证页、JSON/XML 错误响应、空文件及长度不符的文件。
不提供断点续传，也不自动执行网页 JavaScript、验证码或等待队列。

## 镜像、Cookie 与网络

```bash
anna --base-url https://annas-archive.gl doctor
export ANNA_BASE_URL=https://annas-archive.gl
anna --cookies /path/to/cookies.txt search "Pride and Prejudice"
anna --timeout 60 search "Pride and Prejudice"
```

全局参数 `--base-url`、`--cookies`、`--user-agent`、`--timeout` 放在子命令前。
对应环境变量为 `ANNA_BASE_URL`、`ANNA_COOKIES`、`ANNA_USER_AGENT`、`ANNA_TIMEOUT`。
支持标准 `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY` / `NO_PROXY` 和 httpx 的 CA 环境变量。

Cookie 文件必须是浏览器导出的 Netscape 格式，仅发送给匹配的域名和路径，不写入项目。
浏览器验证可能绑定 IP、User-Agent 或浏览器指纹，导出 Cookie 不保证能通过；可使用
`--user-agent` 指定原浏览器 User-Agent。工具不会自动将 Cookie 移植到其他镜像。

默认镜像 `.gl` 可随站点变动而失效，请自行核实新镜像再设置 `--base-url`。
2026-09-12 本机实测：`.gl`、`.gd`、`.pk` 返回 DDoS-Guard 403；`.org` TLS 连接失败；
`.li` 为停放页，`.gs` 为跳转广告页。不能将 HTTP 200 本身视为服务可用。
因此当前**未完成真实站点的搜索/详情/下载成功验收**；本地测试与公网文件下载验证见下方。

## 脚本接口

所有子命令支持 `--json`，全局位置也接受。搜索返回书籍数组，详情返回书籍对象，
链接返回带 `index` 的数组，下载返回 `{path, bytes, md5}`，诊断返回 `{base_url, ok, results}`。
正常输出写 stdout；操作失败退出 1，JSON 模式返回
`{"error":{"type":"ChallengeError","message":"..."}}`。
参数用法错误由 Click 输出到 stderr 并退出 2；Ctrl-C 退出 1。
非 JSON 模式的错误输出到 stderr。

搜索适配公开源码中的列表布局与 `.js-scroll-hidden` 注释结果，强制请求列表模式；
只返回可下载的 `/md5/` 记录，不将 ISBN/DOI 等纯元数据记录当成文件。
详情适配标题区域与 `.js-download-link`；未知布局会报错，不静默返回空结果。
这是 HTML 适配器，站点改版可能需要更新选择器，非 Anna’s Archive 官方项目。

## 开发验证

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv build
```

测试覆盖源码布局形状的匿名化夹具、注释结果去重、筛选与分页请求、Cookie 域隔离、
站点限流/验证页、JSON 错误输出、入口解析、二进制下载、校验失败清理、路径净化和不覆盖。
测试通过 MockTransport，不依赖线上可用性；夹具不是本次联网抓取的成功结果。

2026-09-12 验证结果：30 项测试通过，Ruff 与 wheel/sdist 构建通过；
通过真实 HTTP 重定向从 Project Gutenberg 下载《Pride and Prejudice》无插图 EPUB，
558,381 字节，MD5 `a6409dea67b04c4243504cdfeff33781`，EPUB mimetype 与 ZIP CRC 校验通过。
较大插图版的下载中途断流，已验证错误退出且临时文件被清理。
以上证明通用文件下载链路可用，不代表 Anna’s Archive 的浏览器验证已解决。

解析结构参考公开源码镜像：

- https://github.com/LilyLoops/annas-archive/blob/main/allthethings/templates/macros/aarecord_list.html
- https://github.com/LilyLoops/annas-archive/blob/main/allthethings/page/templates/page/aarecord.html
