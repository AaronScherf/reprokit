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
may not repeat.

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

## Extraction schema and records (screening_pipeline tier)

`evidence/extraction_schema.yaml` declares the fields recorded for every included source. Each field has a `type`
(`string`, `number`, `boolean`, `list`) and an `aggregate` mode (`count`, `sum`, `list`, `none`).

Each included source gets one record, `evidence/extractions/<id>.yaml` (file name = `source_id`), with `extractor`,
`prompt_version`, `source_content_hash`, `cost: {usd}`, `fields` (only declared fields, correct types, flat lists, text
at most 500 characters, in your own words), and `locators` (where in the source each value came from, short text).

A record is **stale** when its `source_content_hash` differs from the manifest entry's `content_hash` (both set). The
source changed since extraction; validation warns (it does not fail) and tells you to re-run extraction for that id.

## `reprokit validate` on an evidence repo

In addition to the usual charter and config checks, validation reports:

- manifest schema errors and the type-specific rules above;
- `synthesis.md` markers that cite missing, non-included or unverified sources;
- extraction schema and record errors, and included sources with no record (add the record, or set the source's
  `screening_status` to `candidate` or `excluded`);
- warnings for stale records, and for `restricted` entries in a public project;
- any `.pdf`, `.epub` or `.docx` file in the repo (outside git-ignored top-level folders and `cache/`);
- a `cache/` directory that is not ignored via a `/cache/` line in `.gitignore`.

## `reprokit evidence-run [repo_dir] [--only a,b] [--exclude c]`

Combines extraction records of `included` sources using each field's `aggregate` mode and writes
`outputs/evidence_aggregate.yaml` (also printed): the source ids used, the combined fields, and total `cost_usd`.
It never calls an AI service. It needs the screening_pipeline tier: on a minimal-tier repo it stops with "add
evidence/extraction_schema.yaml (see docs/evidence-kind.md)" and writes nothing. An id in `--only`/`--exclude` that is not in the manifest is an error. Any selected
included source with no extraction record fails the run and names the source; leave it out with `--exclude`.
With `--only` or `--exclude` the output also contains a `delta`: sources removed, per-field change (numbers
subtract; lists show removed/added) and the cost change. This is a sensitivity check ("what if we dropped this paper?").

## `reprokit verify-sources [repo_dir]`

A separate command because it uses the network. For each `included` source it checks `doi` and `openalex` identifiers
(including `also` entries) with a HEAD request to `https://doi.org/` or `https://api.openalex.org/works/`, and contacts
no other host. Redirects are not followed (a redirect from doi.org already proves the DOI exists). No credentials.
Outcomes: found (silent), **not found** (404/410: check the identifier for typos), or **unreachable** (timeout,
network or server error: the identifier was not judged, try again later). Exit 1 if any problem.

## `reprokit migrate-review REVIEW [--out PATH] [--retrieved-on YYYY-MM-DD] [--status candidate|included] [--force]`

Converts an older `literature_review.md` into a manifest (default output `evidence/manifest.yaml`). It expects blocks
like this (made-up example):

```
### 1. A Study of Something
- **Authors:** Ada Example, Bo Sample
- **Publication Year:** 2020
- **DOI / Link:** [10.1234/abc](https://doi.org/10.1234/abc)
```

Each paper becomes an `article` with id `<first-author-surname>-<year>` (`-b`, `-c` for repeats), `access_class: unknown`,
`screening_status: candidate`, `verification_status: proposed`. A review is a list of search hits, not screening
decisions, so entries start as candidates: mark each one `included` or `excluded` as you screen it. Pass
`--status included` only if you have already screened the whole list (each included source then needs an extraction
record on the screening_pipeline tier). Abstracts and citation counts are dropped. Papers with no
usable DOI or link are skipped with a warning on stderr (add them by hand). It refuses to overwrite an existing output
unless you pass `--force`. Review the result, then run `reprokit validate`.

## Rights rules

- No PDFs, EPUBs, DOCX files or full source text are committed; validation blocks the file types. Keep local copies
  in `cache/`, which is git-ignored (`/cache/` in `.gitignore`).
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
