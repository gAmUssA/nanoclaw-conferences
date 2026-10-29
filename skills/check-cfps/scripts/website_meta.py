"""Read public website descriptions without executing a page.

Importable helper for relevance-gate.py. The caller runs ``--fetch-meta`` in
a child with a 15-second wall deadline. Each hop pins a public DNS result,
allows at most three redirects, and reads at most 256 KiB. Only description
meta tags reach the classifier; an unavailable page supplies no description.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import urllib.parse
from html.parser import HTMLParser

MAX_BYTES = 262_144
MAX_DESCRIPTION = 2_000
FETCH_SECONDS = 15


class DescriptionParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.descriptions: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "meta":
            return
        values = {key.casefold(): value for key, value in attrs}
        key = (values.get("name") or values.get("property") or "").casefold()
        content = values.get("content")
        if key in ("description", "og:description") and content:
            self.descriptions.setdefault(key, " ".join(content.split())[:MAX_DESCRIPTION])

    def description(self):
        return self.descriptions.get("description") or self.descriptions.get("og:description", "")


def public_target(url: str):
    """Resolve once, reject nonpublic destinations, and return a pinned address."""
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(ord(char) < 33 for char in url)
    ):
        raise ValueError("website must be a public HTTP(S) URL without credentials")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in (80, 443):
        raise ValueError("website uses an unsupported port")
    addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("website resolves to a nonpublic destination")
    addresses.sort(key=lambda row: row[0] != socket.AF_INET)
    return parsed, port, str(addresses[0][4][0])


def fetch_description(url: str) -> dict:
    """Bounded child operation. Errors carry only a safe category, never a body."""
    try:
        for hop in range(4):
            parsed, port, address = public_target(url)
            assert parsed.hostname is not None
            conn = http.client.HTTPConnection(parsed.hostname, port, timeout=8)
            try:
                conn.sock = socket.create_connection((address, port), timeout=8)
                if parsed.scheme == "https":
                    conn.sock = ssl.create_default_context().wrap_socket(
                        conn.sock, server_hostname=parsed.hostname
                    )
                target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
                conn.request(
                    "GET",
                    target,
                    headers={"Host": parsed.netloc, "User-Agent": "NanoClaw-CFP/1.0"},
                )
                response = conn.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader("Location")
                    if not location or hop == 3:
                        return {"description": "", "warning": "website redirect limit"}
                    url = urllib.parse.urljoin(url, location)
                    continue
                if response.status != 200:
                    return {"description": "", "warning": f"website HTTP {response.status}"}
                if response.headers.get_content_type() not in (
                    "text/html",
                    "application/xhtml+xml",
                ):
                    return {"description": "", "warning": "website is not HTML"}
                body = response.read(MAX_BYTES + 1)
                charset = response.headers.get_content_charset() or "utf-8"
                parser = DescriptionParser()
                parser.feed(body[:MAX_BYTES].decode(charset, errors="replace"))
                return {
                    "description": parser.description(),
                    "warning": "website preview limited to 256 KiB"
                    if len(body) > MAX_BYTES
                    else "",
                }
            finally:
                conn.close()
    except (OSError, ValueError, LookupError, http.client.HTTPException):
        return {"description": "", "warning": "website metadata unavailable"}
    return {"description": "", "warning": "website redirect limit"}
