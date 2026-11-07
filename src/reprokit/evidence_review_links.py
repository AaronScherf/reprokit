"""DOI / Link field of a literature review: pick one link and turn it into a manifest identifier."""
import re
from urllib.parse import urlparse

_BARE = re.compile(r"https?://\S+|10\.\d{4,9}/\S+")
_DOI = re.compile(r"doi\.org/(10\.\S+)$", re.IGNORECASE)
_OPENALEX = re.compile(r"openalex\.org/(?:works/)?(W\d+)", re.IGNORECASE)
_TRAIL = ".,;:\"'>"  # sentence punctuation, closing quotes and the end of an <autolink>


def _targets(value: str) -> list[str]:
    """URLs of every markdown link on the line; inner balanced parentheses survive."""
    found, pos = [], 0
    while (start := value.find("](", pos)) != -1:
        depth, i = 1, start + 2
        while i < len(value) and depth:
            depth += {"(": 1, ")": -1}.get(value[i], 0)
            i += 1
        if depth == 0:
            found.append(value[start + 2:i - 1].strip())
        pos = start + 2
    return found


def _clean_bare(token: str) -> str:
    token = token.lstrip("<").rstrip(_TRAIL)
    while token.endswith(")") and token.count(")") > token.count("("):
        token = token[:-1].rstrip(_TRAIL)
    return token


def _host_rank(candidate: str) -> int:
    host = urlparse(candidate).hostname or ""
    if host in ("doi.org", "dx.doi.org", "www.doi.org"):
        return 0
    return 1 if host.endswith("openalex.org") else 2


def link(value: str) -> str | None:
    candidates = [t.lstrip("<").rstrip(_TRAIL) for t in _targets(value)]
    if not candidates:
        candidates = [_clean_bare(t) for t in _BARE.findall(value)]
    candidates = [c for c in candidates if c]
    return min(candidates, key=_host_rank) if candidates else None  # min is stable: first wins ties


def identifier(link: str | None) -> dict | None:
    if not link:
        return None
    if m := _DOI.search(link):
        ident = {"scheme": "doi", "value": m.group(1)}
    elif m := _OPENALEX.search(link):
        ident = {"scheme": "openalex", "value": m.group(1)}
    elif re.match(r"10\.\d{4,9}/\S+$", link):
        ident = {"scheme": "doi", "value": link}
    else:
        ident = {"scheme": "url", "value": link}
    return ident if _balanced(ident["value"]) and not re.search(r"\s", ident["value"]) else None


def _balanced(value: str) -> bool:
    depth = 0
    for ch in value:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if depth < 0:
            return False
    return depth == 0
