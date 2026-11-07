import re

from .problems import Problem
from .validate import _VERIFIED_STATES

# A marker is [@id] or [@id1; @id2]; ids are letters, digits, dot, underscore, hyphen.
_MARKER = re.compile(r"\[@([\w.\-]+(?:\s*;\s*@[\w.\-]+)*)\]")


def extract_markers(text: str) -> list[tuple[int, str]]:
    """Return (1-based line number, cited id) for every marker, in order."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    found = []
    for match in _MARKER.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        for cited in re.split(r"\s*;\s*@?", match.group(1)):
            found.append((line, cited))
    return found


def check_claims(text: str, manifest: dict, path: str) -> list[Problem]:
    sources = {s.get("id"): s for s in manifest.get("sources", [])}
    problems = []
    for line, sid in extract_markers(text):
        where = f"line {line}"
        source = sources.get(sid)
        if source is None:
            problems.append(Problem(path, where, f"The claim cites '{sid}', which is not in the evidence manifest. Add it to the manifest or fix the id."))
        elif source.get("screening_status") != "included":
            problems.append(Problem(path, where, f"The claim cites '{sid}', which is {source.get('screening_status')}, not included. Include the source in the manifest or remove the citation."))
        elif source.get("verification_status") not in _VERIFIED_STATES:
            problems.append(Problem(path, where, f"The claim cites '{sid}', which is not yet verified (verification_status is {source.get('verification_status')}). Verify the source or remove the citation."))
    return problems
