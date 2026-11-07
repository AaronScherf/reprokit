# The evidence project kind

An `evidence` project records a body of sources (papers, reports, datasets, web pages) and the claims you make from
them, so another person can see which sources you used, how you checked them, and what each claim rests on.
It is available from reprokit v0.4.0. Everything below runs without any account; nothing here calls an AI service.

## Create a project

Run Copier from a local clone of reprokit (not the git URL, which copies the whole repo root):

```
uv run copier copy template path/to/new-repo
```

Answer `kind: evidence`. For an evidence project you are also asked `screening_pipeline` (default false).

| Tier | You get | Use it when |
| --- | --- | --- |
| Minimal (`screening_pipeline` false) | `evidence/manifest.yaml`, `synthesis.md`, `project.yaml`, notes, a quick check | You list and verify sources by hand and cite them in a write-up. |
| `screening_pipeline` true | Everything above plus `evidence/extraction_schema.yaml`, `evidence/extractions/`, `compute.yaml`, `agents.yaml` | You (or an AI agent) screen sources and extract structured fields, and want them combined with `evidence-run`. |

Neither tier has a `data/` folder. The template's default `reprokit_requirement` pins a released tag; make sure the
tag contains the `evidence` kind (v0.4.0 or later) or the generated quick check will fail with an ImportError.

## The manifest

`evidence/manifest.yaml` is the only list of sources. To keep it elsewhere, set `evidence: {manifest: path}` in
`project.yaml`; the path must be relative and stay inside the repo (absolute paths and `..` that leave the repo are
rejected). `validate`, `evidence-run` and `verify-sources` all read the same file. The extraction schema and records
always stay under `evidence/`, wherever the manifest is. Each entry:

| Field | Meaning |
| --- | --- |
| `id` (required) | Lowercase letters, digits, `_` and `-`, starting with a letter or digit. Unique. This is what you cite. |
| `type` (required) | `article`, `report`, `dataset`, `webpage`, `project_package` or `other`. |
| `identifier` (required) | `{scheme, value}`. Schemes: `doi`, `openalex`, `dataset_doi`, `url`, `file_hash`. |
| `also` | More identifiers for the same source (same shape). |
| `title` (required), `year`, `retrieved_on` | Descriptive. |
| `access_class` (required) | `open`, `paywalled`, `restricted`, `confidential`, `unknown`. |
| `screening_status` (required) | `candidate`, `included`, `excluded`. Add `screening_reason` to say why. |
| `verification_status` (required) | `proposed`, `source-verified`, `fixture-tested`, `run on acquired data`, `independently reproduced`. Anything beyond `proposed` counts as checked. |
| `content_hash`, `converter` | Hash of the local copy you read, and the tool that converted it. Used to detect stale records. |
| `snapshot` | `{url, date}` for a web page as you saw it. |
| `rights_note`, `extraction`, `descriptor` | Free-text rights note; a pointer to extraction data; a link to a dataset descriptor. |

Type-specific rules: a `webpage` marked as checked needs a `snapshot`; a `dataset` needs a `descriptor`. Source ids
may not repeat. `title`, `screening_reason` and `rights_note` are at most 500 characters each.

Pointer checks: a dataset's `descriptor` must be a path inside the repo to a file that exists, and that file is
validated as a dataset descriptor. An `extraction` path must stay inside the repo; on the screening_pipeline tier it
must be exactly `evidence/extractions/<id>.yaml` (the only place records are read) and the file must exist.

Public projects (`confidentiality: public` in `project.yaml`) also get these rules, because every field of an entry
(title, identifier, notes) becomes public:

- Any entry with `access_class: confidential` fails: move it to a private project or remove it.
- An entry with `access_class: restricted` is a warning: check its details may be shown publicly.
- A `project_package` is accepted only as a pointer: `access_class: open` (or `restricted`, with the warning) and no
  `extraction`.

`private_until_release` and `confidential` projects accept all of these.

## Citing sources in synthesis.md

Write claims in `synthesis.md` with a marker after the claim: `[@smith-2020]`, or several at once:
`[@smith-2020; @lee-2019]`. Each cited id must be in the manifest, be `included`, and have a checked
`verification_status`. Unknown, candidate/excluded, or still-`proposed` sources fail validation, with the line number.

Text that looks like a marker but is not one of these two forms (for example `[@smith 2020]` or `[@a, @b]`) is
reported as a malformed citation marker. Fenced code blocks and inline code are ignored, so you can show a marker
inside backticks. The malformed check works one line at a time on purpose: a marker split across two lines is not
reported.

## Extraction schema and records (screening_pipeline tier)

`evidence/extraction_schema.yaml` declares the fields recorded for every included source. Each field has a `type`
(`string`, `number`, `boolean`, `list`) and an `aggregate` mode (`count`, `sum`, `list`, `none`). The schema may also
set `extractor` and `prompt_version`: the extractor and prompt version every record is expected to have.

Each included source gets one record, `evidence/extractions/<id>.yaml` (file name = `source_id`), with `extractor`,
`prompt_version`, `source_content_hash`, `cost: {usd}`, `fields` (only declared fields, correct types, flat lists, text
in your own words), and `locators` (where in the source each value came from, short text). Size limits: each text
value in `fields`, each locator, `extractor` and `prompt_version` at most 500 characters; `source_content_hash` at
most 128; and at most 4000 characters of text in the whole record. Numbers must be finite (no nan or inf).

These are problems, not warnings: a record whose `source_id` is not in the manifest; a file in
`evidence/extractions/` that does not end in `.yaml` (`.gitkeep` and OS files such as `.DS_Store` and `Thumbs.db`
are allowed).

A record is **stale** when its `source_content_hash` differs from the manifest entry's `content_hash` (both set), or
when the schema sets `extractor` or `prompt_version` and the record's value differs. Validation warns (it does not
fail) and tells you to re-run extraction for that id.

## `reprokit validate` on an evidence repo

In addition to the usual charter and config checks, validation reports:

- manifest schema errors and the type-specific rules above;
- `synthesis.md` markers that cite missing, non-included or unverified sources;
- extraction schema and record errors, and included sources with no record (add the record, or set the source's
  `screening_status` to `candidate` or `excluded`);
- warnings for stale records, and for `restricted` entries in a public project;
- any source document in the repo: `.pdf`, `.epub`, `.docx`, `.doc`, `.rtf`, `.odt`, `.djvu`, `.mobi`, `.azw3`,
  `.ps`, `.xps` (any letter case; `cache/` and top-level folders that `.gitignore` ignores by name are skipped);
- a `cache/` directory that `.gitignore` does not ignore. Accepted lines: `/cache/`, `/cache`, `cache/` or `cache`.
  Trailing spaces are dropped as git does; a trailing tab is not, so `cache` followed by a tab does not count;
- a `!` line in `.gitignore` that could re-include files under `cache/`: a glob or escaped pattern, or one that
  starts with `cache`. A literal path outside `cache/`, such as `!.env.example`, is fine.

`validate` prints warnings with the rest of its report on stdout. `evidence-run` and `verify-sources` print
warnings (restricted entries, stale records, the primary-identifier warning below) on stderr, each ending in
`[warning]`, so their stdout can be redirected cleanly.

## `reprokit evidence-run [repo_dir] [--only a,b] [--exclude c]`

Combines extraction records of `included` sources using each field's `aggregate` mode and writes
`outputs/evidence_aggregate.yaml` (also printed): the source ids used, the combined fields, and total `cost_usd`.
It never calls an AI service. It needs the screening_pipeline tier: on a minimal-tier repo it stops with "add
evidence/extraction_schema.yaml (see docs/evidence-kind.md)" and writes nothing. An id in `--only`/`--exclude` that
is not in the manifest is an error, and so is an empty `--only` or `--exclude` (for example `--only ""` or
`--only ,`). Any selected included source with no extraction record fails the run and names the source; leave it
out with `--exclude`. With `--only` or `--exclude` the output also contains a `delta`: sources removed, per-field
change (numbers subtract; lists show removed/added) and the cost change. This is a sensitivity check ("what if we
dropped this paper?"). Sums, deltas and costs are rounded to 6 decimal places so float noise does not show. The
output file is written with LF line endings on every platform.

## `reprokit verify-sources [repo_dir]`

A separate command because it uses the network. For each `included` source it checks `doi` and `openalex` identifiers
(including `also` entries) with a HEAD request to `https://doi.org/` or `https://api.openalex.org/works/`, and contacts
no other host. Redirects are not followed (a redirect from doi.org already proves the DOI exists). No credentials.
An `openalex` value must be `W` followed by digits, or a full `https://openalex.org/W...` or
`https://api.openalex.org/works/W...` URL (stripped to the W-id; the `W` may be lower case). Anything else is
reported as "not a valid OpenAlex id" and no request is made.

A source passes when any of its identifiers is found. When none is, one problem names every identifier tried as
`scheme:value`, with the outcome: **invalid identifier** (malformed value: fix it in the manifest), **unreachable**
(timeout, network or server error: the identifier was not judged, try again later), or **not found** (404/410:
check the identifier for typos). If the primary `identifier` fails but an `also` one is found, the source passes
with a warning: `primary identifier <scheme:value> of '<id>' did not resolve; <scheme:value> did`.

It ends with a summary line on stdout, also on a clean run: `checked N sources (S skipped: <schemes>)`, where
skipped sources are included ones with no `doi` or `openalex` identifier (for example only `url` or `file_hash`).
Exit 1 if any problem.

## `reprokit migrate-review REVIEW [--out PATH] [--retrieved-on YYYY-MM-DD] [--status candidate|included] [--force]`

Converts an older `literature_review.md` into a manifest (default output `evidence/manifest.yaml`). It expects blocks
like this (made-up example):

```
### 1. A Study of Something
- **Authors:** Ada Example, Bo Sample
- **Publication Year:** 2020
- **DOI / Link:** [10.1234/abc](https://doi.org/10.1234/abc)
```

A `###` heading starts a paper only if it carries the `<a id="paper-N"></a>` anchor or its block has an `Authors`,
`Publication Year` or `DOI / Link` field; other `###` headings (search notes and the like) are ignored and not
counted as skipped. Quotes and angle brackets around a link are removed, so `"https://doi.org/10.1234/abc"` and
`<https://doi.org/10.1234/abc>` both give the DOI `10.1234/abc`.

Each paper becomes an `article` with id `<first-author-surname>-<year>` (`-b`, `-c` for repeats), `access_class: unknown`,
`screening_status: candidate`, `verification_status: proposed`. The surname skips trailing `et al.`, `Jr.`, `Sr.`,
`II` and `III`, and is folded to ASCII (`ø`, `ß`, `ł`, `æ`, `œ`, `đ`, `þ`, `ð` become `o`, `ss`, `l`, `ae`, `oe`,
`d`, `th`, `d`; other accents are dropped), so `Sørensen` gives `sorensen`. A review is a list of search hits, not screening
decisions, so entries start as candidates: mark each one `included` or `excluded` as you screen it. Pass
`--status included` only if you have already screened the whole list (each included source then needs an extraction
record on the screening_pipeline tier). Abstracts and citation counts are dropped. Papers with no
usable DOI or link are skipped with a warning on stderr (add them by hand). `--retrieved-on` must be a real date
written `YYYY-MM-DD` (default: today). A review saved with a UTF-8 byte-order mark is read normally, and the manifest
is written with LF line endings. It refuses to overwrite an existing output unless you pass `--force`. Review the
result, then run `reprokit validate`.

## Rights rules

- No source documents (the file types listed under `validate` above) or full source text are committed; validation
  blocks the file types. Keep local copies in `cache/`, which is git-ignored (`/cache/` in `.gitignore`).
  Plain-text and HTML transcriptions (.txt, .md, .html) are NOT detected by the guard, so keep them under the
  gitignored `cache/`.
- Abstracts are never stored. Re-fetch them from the source by identifier.
- Extraction text is short (500 characters) and in your own words; record where it came from in `locators`.
- A public project lists no `confidential` entries, and a project package only as a pointer (no `extraction`).
  Confidential material belongs in a private project.

## Zotero is optional

The manifest is the only source of truth. You may keep a Zotero library for your own reading, but reprokit does not
read it, and a reproduction never needs it. If you ever use a Zotero API key, keep it only in `.env` (git-ignored);
it must never be written to a committed file or a log.

## Cost transparency

Screening or extraction with an AI service costs money. Record those costs in `compute.yaml` and per record in
`cost.usd`. Anything estimated over $1 needs the project owner's go-ahead first.

## Not in v0.4.0

- Source adapters that fetch or transcribe sources.
- OpenAlex search for finding candidate sources.
- Zotero sync.
- The `library` project kind.
- The 3ie taxonomy hooks.
