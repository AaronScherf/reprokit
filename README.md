# reprokit

Schemas, validators, a small CLI, and a repo template for reproducible research projects. It checks the
files that make a project understandable and re-runnable by someone else, human or AI agent: the project
charter, data descriptors, run configs, harmonization records, run manifests, and compute and AI-use profiles.

Status: v0.3.0. Python 3.11 or newer.

## Install

```
uv sync --locked
uv run reprokit validate path/to/repo
```

## Start a new project

```
uv run copier copy template path/to/new-repo
```

You are asked for the project name, purpose, confidentiality class (required, no default), author and
license year. The generated repo has the folder layout, `AGENTS.md` rules for agents, a locked-environment
setup, and CI that runs `reprokit validate` and a secret scan. In the new repo run `uv lock` once and commit
`uv.lock`.

## Commands

| Command | What it does |
| --- | --- |
| `reprokit validate [repo_dir]` | Checks `project.yaml`, `compute.yaml`, `agents.yaml`, `config.yaml` and every `data/descriptors/*.yaml`, and for each `instances/<name>/` its `config.yaml`, `data/descriptors/*.yaml` and `harmonization/*.yaml`. Exit 0 if clean, 1 otherwise. A missing directory is an error. |
| `reprokit quick-check [repo_dir]` | Runs the project's `quick_check.py` on made-up data and prints a plain PASS or FAIL message. The generated template supplies a working placeholder that must be replaced before it says anything about the project. |
| `reprokit gate --baseline instances/a/config.yaml --config instances/b/config.yaml --records instances/b/harmonization` | Compares the two configs' providers by role. A provider change, or a role added or removed, needs a harmonization record named `<role>.yaml` in the records folder. Exit 1 and one line per missing or invalid record otherwise. Case and surrounding spaces in provider names are ignored. |
| `reprokit manifest --config config.yaml --raw-dir data/raw --out outputs/manifest.json` | Hashes the files under `data/raw/<role>/` for each role in the config and writes a run manifest (code version, parameters, input hashes, installed package versions). |

## Reading the output

Every problem is one line: `file: field: message`. For example:

```
config.yaml: period.end: 'tomorrow' is not a 'date'
data/descriptors/acled.yaml: accessed: 'accessed' is a required property
```

The same text is meant for people and agents: it names the file, the field and what was expected.

## The documents

All documents are YAML and carry `schema_version` (SemVer). Unknown keys are rejected, so typos fail loudly.
Dates are written `2026-10-31`; duplicate keys are an error.

| File | Schema | What it holds |
| --- | --- | --- |
| `project.yaml` | `charter` | Name, kind, purpose, confidentiality class, audiences, publication plan, deliverables, taxonomy tags, sources, sibling repos. Extra rules: deliverable audiences must exist; a `confidential` project's public deliverable needs `requires_redaction: true`; academic purposes need a venue or preregistration. |
| `data/descriptors/*.yaml` | `descriptor` | One data source: role, provider, query, coverage, variables with meaning and unit, access class, reuse terms, verification state, and `find_in_other_geography`. Account-gated or by-request sources also need `accessed`, `applied_filters` and `manipulation`. |
| `config.yaml` | `config` | Geography, period (start not after end), sources by role (`provider`, `dataset`), free-form `parameters`. Inputs are found by role directory, never by file name. |
| `harmonization/<role>.yaml` | `harmonization` | Record required when a role's provider changes, or a role is added or removed: differences, decision, rationale, affected outputs, approver. See `reprokit.harmonization.check_gate`. |
| `outputs/manifest.json` | `manifest` | What a run used: code version, parameters, input hashes per role, installed packages. |
| `compute.yaml` | `compute` | Local limits, backend preference order, backend access and cost notes. See `reprokit.profiles.choose_backend`. |
| `agents.yaml` | `agents` | AI subscriptions, local-or-API preference, spend warn threshold and ceiling, and whether restricted data may go to external AI (default no). See `reprokit.profiles.check_spend`. |

For descriptors at `source-verified` or a higher verification state, `validate` rejects `access_class: unverified` and blank or placeholder `reuse_terms` (including `confirm`, `verify`, `unverified`, and `TBD`). Placeholders remain valid while a descriptor is `proposed`.

Descriptor schema `0.2.0` adds `coverage_period: {start, end}` with ISO dates, optional `coverage_gap_note`, and `verification_note` as a project-root-relative path. At `source-verified` or higher, `validate` requires the coverage period to span the matching config period unless a nonblank gap note explains the difference. It also requires an existing verification note containing the descriptor's exact status string. These checks do not apply to `0.1.0` descriptors. The schema version is independent of the reprokit package version.

The `verification_note` check proves only that the file exists and contains the status string. It does not prove the claim is true: a note saying `NOT yet run on acquired data` passes that check.

Charter schema `0.2.0` adds one line, `quick_check: <command>`, required when any deliverable has a build command. Older charters still validate, with a notice that the quick check requirement did not run.

After `reproduce`, a project can call `reprokit.run_summary.write_run_summary(...)` to make `RUN_SUMMARY.md` from its manifest, run report, settings, and versioned `run_metrics.json`. The summary tells a reader what the run produced and what it cost. Missing measurements and mismatched output checksums stop the renderer with a plain explanation. The project records timings and memory; reprokit does not measure them. See [the interface note](docs/quick-check-run-summary-proposal.md).

Verification states used in descriptors and results: `proposed`, `source-verified`, `fixture-tested`,
`run on acquired data`, `independently reproduced`.

## Development

```
uv run pytest
uv run ruff check
```

Schemas change only with a version bump and a test. See `AGENTS.md`.
