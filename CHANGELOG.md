# Changelog

All notable changes to this project are documented here. Format follows Keep a Changelog; versions follow SemVer.

## [0.4.0] - Unreleased

- New `evidence` project kind: a source manifest (`evidence/manifest.yaml`), `[@id]` citation markers in `synthesis.md`
  checked against it, and an optional `screening_pipeline` tier with an extraction schema, per-source extraction
  records and `compute.yaml`/`agents.yaml`. See `docs/evidence-kind.md`.
- `reprokit validate` for evidence repos: manifest and type rules, claim citations, extraction records, stale-record
  warnings, and blocks on committed PDF/EPUB/DOCX files and an un-ignored `cache/`.
- `reprokit evidence-run` combines extraction records (`--only`/`--exclude` with a sensitivity delta; never calls AI).
- `reprokit verify-sources` checks DOIs and OpenAlex ids online (only doi.org and api.openalex.org).
- `reprokit migrate-review` converts a `literature_review.md` into a manifest, dropping abstracts.
- Not included: fetching/transcribing source adapters, OpenAlex search, Zotero sync, the `library` kind, 3ie taxonomy hooks.
- Release note: the template's default `reprokit_requirement` still pins v0.3.2. It MUST be bumped to the v0.4.0 tag at
  release, otherwise a generated evidence repo's quick check fails with an ImportError on `reprokit.evidence_*`.

## [0.3.2] - 2026-11-06

- Add `reprokit.env.load_project_env(root)` for simple project `.env` files. Existing environment variables win;
  missing files are allowed, a UTF-8 BOM is accepted, unsupported `export` lines are skipped, and values are never logged.
- Explain account setup and multi-source fetch behavior in generated project guidance, including manual downloads and
  how to handle failures without stopping public sources.
- `reprokit validate` warns when an account-required or request-required descriptor lacks README acquisition guidance.
  The warning does not change a passing project's exit status.

## [0.3.1] - 2026-11-05

- New projects keep data files and test examples byte-for-byte across computers, so Git on Windows cannot change their checksums just by checking them out.
- When a run file's checksum differs only because its line endings changed, the summary names the file, explains the likely Windows Git cause, and tells you how to restore it. Other mismatches still stop with the original warning.

## [0.3.0] - 2026-11-05

A new project can check its setup with one quick command and read a short summary of a real run. The quick check uses invented data, so a PASS confirms the software setup works; it does not confirm the research results. Source checks now catch licence placeholders and missing explanations before a source is treated as checked.

### For researchers

- `reprokit quick-check` runs the project's made-up-data check and explains PASS or FAIL in plain language, including what to do next. The generated project's `quick_check.py` is a working placeholder that says it must be replaced before its PASS is used as project evidence.
- A project can generate `RUN_SUMMARY.md` with `write_run_summary`. It explains the study dates, final row count, output checksums, and measured time and memory without hand-entered figures.
- `reprokit validate` flags blank or placeholder licence terms and unverified access text when a source is marked `source-verified` or higher. Descriptor schema `0.2.0` also checks whether source coverage spans the configured period, unless a gap is explained, and whether a verification note exists and names the status. The note check confirms the text is present; it does not prove the claim is true.

### Technical changes

- Charter schema `0.2.0` requires a one-line `quick_check: <command>` when any deliverable lists a build. Validation also checks that `quick_check.py` exists when that line is set.
- The run summary renderer reads the internal `run_metrics.json` contract version `0.1.0`: per-step elapsed time, peak RSS and its process/tree basis, measurement date (including carried-forward measurements for skipped steps), and output SHA-256 values. It fails when required measurements are missing.
- The template includes a rewritten README, `quick_check.py`, a starter unit test, and Windows/Linux CI in this order: `uv sync --locked`, quick-check (60-second limit), validate, pytest.
- New generated projects pin the reprokit `v0.3.0` Git tag.

### Upgrading existing projects

- Descriptor and charter documents on schema `0.1.0` still validate. Checked `0.1.0` descriptors get one notice that coverage and verification-note checks were skipped; `0.1.0` charters get one notice that the quick-check requirement was skipped. The licence and access-text checks still apply to checked descriptors on either schema version.
- To adopt descriptor schema `0.2.0`, change `schema_version`, add `coverage_period: {start, end}`, add `coverage_gap_note` if the source does not cover the configured period, and point `verification_note` to a project file that names the exact verification status. To adopt charter schema `0.2.0`, change `schema_version` and add a one-line `quick_check` command when a deliverable has a build; add `quick_check.py` for that command. Update the project's reprokit dependency and lockfile to pin the `v0.3.0` tag.

## [0.2.0] - 2026-10-31

### Added
- `validate` walks `instances/*/` (config, descriptors, harmonization records).
- `reprokit gate` command: harmonization records required against a baseline config.

### Changed
- The template's default `reprokit_requirement` pins `v0.2.0`.

## [0.1.0] - 2026-10-31

### Added
- Schemas and validators for the project charter, data descriptor, run config, harmonization record, run
  manifest, compute profile and agent profile.
- Cross-field rules for charters (audiences, confidentiality, publication) and configs (period order).
- Harmonization gate: provider changes and added or removed roles require a record.
- Run manifest with per-role input hashes and installed package versions.
- Backend choice from a compute profile; spend check (ok, confirm above the warn threshold, refuse above the ceiling).
- `reprokit validate` and `reprokit manifest` commands.
- Copier template: folder layout, `AGENTS.md` with derivative rules and the restricted-data AI rule, locked
  environment setup, CI with secret scanning.
- Descriptor provenance fields (`accessed`, `applied_filters`, `manipulation`) required for gated sources.
- `restricted_data_to_external_ai` flag in the agent profile.

### Fixed
- YAML dates stay strings; duplicate keys and impossible dates are rejected.
- Negative or NaN spend estimates are rejected.
- `validate` fails on a missing directory.
