import re

from .problems import Problem
from .validate import VERIFIED_STATES

# A marker is [@id] or [@id1; @id2]; ids are letters, digits, dot, underscore, hyphen.
_MARKER = re.compile(r"\[@([\w.\-]+(?:\s*;\s*@[\w.\-]+)*)\]")
# Anything that looks like a marker on one line; reported when it is not a valid marker.
# Deliberately single-line: a match allowed to cross newlines could swallow far-away text up to
# the next ']' and report it as one huge "marker", so marker-like text split over lines is not reported.
_LOOSE = re.compile(r"\[@[^\]\n]*\]")
# A backtick fence's info string cannot contain a backtick (CommonMark), so "```code``` text" is an
# inline span, not a fence opener.
_FENCE = re.compile(r"^ {0,3}(?:(`{3,})[^`]*$|(~{3,}).*$)")
_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*$")
_SPAN = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)")


def _blank(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def _without_code(text: str) -> str:
    """Normalize newlines and blank out fenced code blocks and inline code spans, keeping line numbers."""
    lines, fence = text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), None
    for index, line in enumerate(lines):
        opening = _FENCE.match(line)
        if fence is None and opening:
            fence = opening.group(1) or opening.group(2)
        elif fence is not None:
            closing = _CLOSE.match(line)
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= len(fence):
                fence = None
        else:
            continue
        lines[index] = _blank(line)
    return _SPAN.sub(lambda m: _blank(m.group()), "\n".join(lines))


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def extract_markers(text: str) -> list[tuple[int, str]]:
    """Return (1-based line number, cited id) for every marker outside code, in order."""
    text = _without_code(text)
    found = []
    for match in _MARKER.finditer(text):
        for cited in re.split(r"\s*;\s*@?", match.group(1)):
            found.append((_line(text, match.start()), cited))
    return found


def malformed_markers(text: str) -> list[tuple[int, str]]:
    """Return (line, text) for marker-like text outside code that is not [@id] or [@id1; @id2]."""
    text = _without_code(text)
    return [(_line(text, m.start()), m.group()) for m in _LOOSE.finditer(text) if not _MARKER.fullmatch(m.group())]


def check_claims(text: str, manifest: dict, path: str) -> list[Problem]:
    sources = {s.get("id"): s for s in manifest.get("sources", [])}
    found = []
    for line, sid in extract_markers(text):
        source = sources.get(sid)
        if source is None:
            found.append((line, f"The claim cites '{sid}', which is not in the evidence manifest. Add it to the manifest or fix the id."))
        elif source.get("screening_status") != "included":
            found.append((line, f"The claim cites '{sid}', which is {source.get('screening_status')}, not included. Include the source in the manifest or remove the citation."))
        elif source.get("verification_status") not in VERIFIED_STATES:
            found.append((line, f"The claim cites '{sid}', which is not yet verified (verification_status is {source.get('verification_status')}). Verify the source or remove the citation."))
    for line, marker in malformed_markers(text):
        found.append((line, f"malformed citation marker '{marker}' on line {line}; write [@id] or [@id1; @id2]"))
    return [Problem(path, f"line {line}", message) for line, message in sorted(found, key=lambda item: item[0])]
