# Proposed interface for run card and smoke (review before implementation)

## Current evidence

`reprokit` provides `build_manifest` and validation, but no pipeline runner. The project owns `reproduce` through `doit`. Its current `manifest.json` has code/input hashes but no output hashes or window; its `run_report.json` has aggregate stats and decisions but no step timings or peak memory. Neither file alone can support the requested card without new project-side measurements.

## Run card

| Responsibility | Proposed interface |
| --- | --- |
| reprokit | Provide a renderer `write_run_card(manifest_path, report_path, metrics_path, config_path, out_path)` and a versioned `run_metrics.json` contract. Validate required fields and fail clearly when measurements are absent. Render a short Markdown card with window, row counts, output SHA-256 values, per-step elapsed time and peak process-tree RSS, code version, and input manifest reference. |
| project | `reproduce` measures each step, writes `run_metrics.json` with the memory measurement basis, hashes final outputs, calls the renderer after successful steps, and writes `run_card.md` beside its outputs. The project chooses step names and row-count meanings. |

The renderer reads the window from `config.yaml` and hashes from the project's measured output entries. It must not infer missing measurements or copy values from README prose. The run card itself is excluded from its output-hash list. README and verification-note stubs link to the generated card; they contain no hand-typed window, count, or runtime. An unchanged rerun may reuse recorded measurements only when the manifest inputs, code version, config and output hashes still match; otherwise it must rerun or mark the card stale.

## Smoke

| Responsibility | Proposed interface |
| --- | --- |
| reprokit | Ship a synthetic-fixture convention and a small verifier for the smoke result: offline flag, success status, required outputs and hashes. Add a smoke field to the charter schema, required when a deliverable lists a build. The template provides the CI and README command shape. |
| project | Implement one `smoke` CLI command that runs its own full pipeline on synthetic input in an isolated temporary directory, with fetch/network paths disabled. It validates the outputs and returns nonzero on any failure. |

The template cannot supply a working scientific pipeline, so a newly generated project needs to fill in its synthetic adapter and expected output checks when it adds a deliverable build. CI runs `uv sync --locked` then the same smoke command on Windows and Linux, with a 60-second limit. The command must be safe to repeat and must not write into real instance inputs or outputs.

## Decisions accepted 2026-11-03

1. Measurements live in a separate `run_metrics.json`.
2. Memory is peak process-tree RSS, with the measurement basis recorded.
3. Smoke is required when `project.yaml` lists a deliverable build; the charter gets a smoke field.

This is an interface proposal only. The run card and smoke implementation remain unbuilt pending review.
