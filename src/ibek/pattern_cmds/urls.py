"""
URL checks shared by the ``runtime-lock.yaml`` reader and the schema fetcher.

Schema URLs and image refs are repository text, so every URL ibek fetches a
schema from must be an ``https://`` URL that the standard parsers agree on:
no user information and no backslash, both of which different URL parsers
split differently.
"""

from __future__ import annotations

from urllib.parse import urlsplit

HTTPS_PORT = 443


def url_problem(url: str) -> str | None:
    """Return why ``url`` may not be fetched, or None if it may."""
    if "\\" in url:
        return "contains a backslash"
    if any(ord(char) <= 32 or ord(char) == 127 for char in url):
        return "contains whitespace or a control character"
    try:
        parts = urlsplit(url)
    except ValueError:
        # For example a netloc that NFKC normalisation changes, such as a
        # fullwidth "#" before "@".
        return "cannot be parsed"
    if parts.scheme.lower() != "https":
        return "is not an https:// URL"
    if "@" in parts.netloc:
        return "contains user information (user@)"
    if not parts.hostname:
        return "has no host"
    try:
        _ = parts.port
    except ValueError:
        return "has an invalid port"
    return None


def origin_key(host: str, port: int | None) -> str:
    """``host`` for the default HTTPS port, else ``host:port``, lowercased."""
    host = host.lower()
    return host if port in (None, HTTPS_PORT) else f"{host}:{port}"


def url_origin_key(url: str) -> str:
    """The :func:`origin_key` of an https URL."""
    parts = urlsplit(url)
    return origin_key(parts.hostname or "", parts.port)


def host_entry_key(entry: str) -> str | None:
    """Normalise a ``host[:port]`` entry to its :func:`origin_key`.

    Returns None for an entry that is not a plain host and optional port.
    """
    entry = entry.strip()
    if not entry or url_problem(f"https://{entry}/") is not None:
        return None
    parts = urlsplit(f"https://{entry}/")
    if parts.netloc != entry and parts.netloc.lower() != entry.lower():
        return None
    return origin_key(parts.hostname or "", parts.port)
