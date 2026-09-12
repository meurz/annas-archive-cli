import hashlib
import json
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from anna import cli
from anna.client import Client, safe_filename
from anna.errors import AnnaError, ChallengeError, ParseError
from anna.parsing import parse_info, parse_search, record_id

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://archive.example"
MD5 = "1" * 32
BOOK = b"%PDF-1.7\npublic-domain test content\n%%EOF"
CHALLENGE = '<title>DDoS-Guard</title><script src="/ddos-guard/check.js"></script>'


def fixture(name):
    return (FIXTURES / f"{name}.html").read_text()


def client(handler):
    return Client(BASE, transport=httpx.MockTransport(handler))


def test_search_hidden_results_and_metadata():
    books = parse_search(fixture("search"), BASE)
    assert len(books) == 2
    assert books[0].title == "Pride & Prejudice"
    assert books[0].author == "Jane Austen"
    assert books[0].publisher == "Example Press, 1813"
    assert (books[1].language, books[1].format, books[1].size) == ("zh", "pdf", "5.6 MB")
    assert books[0].cover_url == BASE + "/covers/one.jpg"


def test_info_links_and_search_icons():
    book = parse_info(fixture("info"), BASE, MD5)
    assert book.title == "Pride & Prejudice"
    assert book.author == "Jane Austen"
    assert [link.kind for link in book.links] == ["fast", "slow", "external"]
    assert book.links[1].url.startswith(BASE + "/slow_download/")
    assert book.description == "Description A novel."


@pytest.mark.parametrize(
    "html,error",
    [
        (CHALLENGE, ChallengeError),
        ("<title>Loading...</title>Click for continue", ParseError),
        ("This domain may be for sale", ParseError),
        ('<form action="/search">Sign in</form>', ParseError),
    ],
)
def test_non_results_are_errors(html, error):
    with pytest.raises(error):
        parse_search(html, BASE)


def test_real_empty_result():
    assert parse_search("<h1>No files found.</h1>", BASE) == []


def test_record_id_validation():
    assert record_id(BASE + "/md5/" + "A" * 32 + "?x=1") == "a" * 32
    with pytest.raises(AnnaError):
        record_id("this is not a hash")
    with pytest.raises(AnnaError):
        record_id("https://[")


def test_search_request():
    def handler(request):
        assert request.url.params.get_list("ext") == ["epub", "pdf"]
        assert request.url.params["q"] == "中文 & Austen"
        assert request.url.params["page"] == "2"
        assert request.url.params["display"] == ""
        return httpx.Response(200, text=fixture("search"))

    with client(handler) as api:
        assert len(api.search("中文 & Austen", ext=("epub", "pdf"), page=2)) == 2


@pytest.mark.parametrize(
    "status,body,error",
    [
        (403, CHALLENGE, ChallengeError),
        (429, "limited", AnnaError),
        (404, "not found", AnnaError),
        (200, CHALLENGE, ChallengeError),
    ],
)
def test_http_errors(status, body, error):
    with client(lambda r: httpx.Response(status, text=body)) as api:
        with pytest.raises(error):
            api.search("test")


def test_download_redirect_and_checksum(tmp_path):
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/file"})
        return httpx.Response(
            200,
            content=BOOK,
            headers={
                "content-type": "application/pdf",
                "content-disposition": "attachment; filename*=UTF-8''..%2F%E4%B9%A6.pdf",
            },
        )

    with client(handler) as api:
        result = api.download(
            BASE + "/start", directory=tmp_path, expected_md5=hashlib.md5(BOOK).hexdigest()
        )
    assert Path(result["path"]).name == "书.pdf"
    assert Path(result["path"]).read_bytes() == BOOK
    assert result["bytes"] == len(BOOK)
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize(
    "body,headers",
    [
        (CHALLENGE.encode(), {"content-type": "text/html"}),
        (b"<html>Login</html>", {"content-type": "application/octet-stream"}),
        (b'{"error":"denied"}', {"content-type": "application/json"}),
        (b"", {}),
        (BOOK, {"content-length": "1000"}),
    ],
)
def test_invalid_download_never_publishes(tmp_path, body, headers):
    with client(lambda r: httpx.Response(200, content=body, headers=headers)) as api:
        with pytest.raises(AnnaError):
            api.download(BASE + "/file", directory=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_hash_failure_and_no_overwrite(tmp_path):
    output = tmp_path / "book.pdf"
    with client(lambda r: httpx.Response(200, content=BOOK)) as api:
        with pytest.raises(AnnaError, match="MD5"):
            api.download(BASE + "/file", output=output, expected_md5=MD5)
        assert list(tmp_path.iterdir()) == []
        output.write_bytes(b"original")
        with pytest.raises(AnnaError, match="已存在"):
            api.download(BASE + "/file", output=output)
        assert output.read_bytes() == b"original"


def test_explicit_download_button(tmp_path):
    def handler(request):
        if request.url.path == "/landing":
            return httpx.Response(
                200,
                text='<a id="download" href="/file">Download</a>',
                headers={"content-type": "text/html"},
            )
        return httpx.Response(200, content=BOOK)

    with client(handler) as api:
        result = api.download(BASE + "/landing", directory=tmp_path)
    assert Path(result["path"]).read_bytes() == BOOK


def test_interrupted_download_cleans_temp_file(tmp_path):
    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield BOOK * 2000  # Enough data to open the temporary file.
            raise httpx.ReadError("connection lost")

    with client(lambda r: httpx.Response(200, stream=BrokenStream())) as api:
        with pytest.raises(httpx.ReadError):
            api.download(BASE + "/file", directory=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_cookie_domain_isolation_on_redirect(tmp_path):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\narchive.example\tFALSE\t/\tTRUE\t0\tsession\ttest-value\n"
        "archive.example\tFALSE\t/\tTRUE\t1\texpired\tdo-not-send\n"
    )

    def handler(request):
        if request.url.host == "archive.example":
            assert request.headers.get("cookie") == "session=test-value"
            return httpx.Response(302, headers={"location": "https://files.example/file"})
        assert "cookie" not in request.headers
        return httpx.Response(200, content=BOOK)

    with Client(BASE, cookies=cookie_file, transport=httpx.MockTransport(handler)) as api:
        api.download(BASE + "/file", directory=tmp_path)


def test_download_http_challenge(tmp_path):
    with client(lambda r: httpx.Response(403, text=CHALLENGE)) as api:
        with pytest.raises(ChallengeError):
            api.download(BASE + "/file", directory=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_filename_sanitizing():
    assert safe_filename("../../file.pdf") == "file.pdf"
    assert safe_filename("..\\file.pdf") == "file.pdf"
    assert safe_filename("\x00../") == "download.bin"
    assert len(safe_filename("书" * 300).encode()) <= 180


def test_cli_json_and_error(monkeypatch):
    monkeypatch.setattr(
        cli, "Client", lambda **kw: client(lambda r: httpx.Response(200, text=fixture("search")))
    )
    runner = CliRunner()
    result = runner.invoke(cli.main, ["search", "Austen", "--limit", "1", "--json"])
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)) == 1
    monkeypatch.setattr(
        cli, "Client", lambda **kw: client(lambda r: httpx.Response(403, text=CHALLENGE))
    )
    for args in [["--json", "doctor"], ["doctor", "--json"]]:
        result = runner.invoke(cli.main, args)
        assert result.exit_code == 1
        assert json.loads(result.output)["error"]["type"] == "ChallengeError"


def test_cli_record_download_selects_source_and_verifies(tmp_path, monkeypatch):
    digest = hashlib.md5(BOOK).hexdigest()

    def handler(request):
        if request.url.path.startswith("/md5/"):
            return httpx.Response(200, text=fixture("info"))
        assert request.url.host == "files.example"
        return httpx.Response(200, content=BOOK)

    monkeypatch.setattr(cli, "Client", lambda **kw: client(handler))
    output = tmp_path / "book.pdf"
    result = CliRunner().invoke(
        cli.main, ["download", digest, "--source", "3", "-o", str(output), "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["md5"] == digest
    assert output.read_bytes() == BOOK


@pytest.mark.parametrize(
    "args",
    [
        ["search", "test", "--page", "0"],
        ["search", "test", "--limit", "0"],
        ["--timeout", "0", "doctor"],
    ],
)
def test_bad_options(args):
    assert CliRunner().invoke(cli.main, args).exit_code == 2
