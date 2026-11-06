# Quick check and run summary interface

## What a researcher sees

The generated README gives one quick-check command and a link to `RUN_SUMMARY.md`. The quick check says in plain sentences whether made-up data reached a final table, what that proves, and what to do after a failure. The run summary states the study window, final row count, output checksums, time, and memory. The underlying JSON files stay out of the researcher's reading path.

The template's working placeholder prints: "This is the template's placeholder. It checks nothing about your project yet. Replace it before relying on this as evidence." A project replaces that placeholder when it adds its own build.

## Responsibilities

| Part | reprokit supplies | The project supplies |
| --- | --- | --- |
| Quick check | A plain-language result verifier, a `quick_check` charter rule, and a template command and CI job with a 60-second limit. | Made-up raw input, a small end-to-end run, and a result with offline and success flags, elapsed time, required outputs, and checksums. |
| Run summary | `write_run_summary(manifest_path, report_path, metrics_path, config_path, out_path)` and validation for versioned `run_metrics.json`. | `reproduce` records per-step elapsed time, peak RSS, `rss_basis` (`process` or `tree`), output hashes, and the date of each measurement. A skipped step retains its last measurement and date. |

The renderer fails when a required measurement is absent. It reads the window from config, row count from the run report, hashes and timings from metrics, and code version from the manifest. It checks output hashes against files and never uses prose as data. `RUN_SUMMARY.md` is excluded from the output hash list. README and verification-note stubs link to it and contain no hand-typed counts, windows, or runtimes.

## Internal `run_metrics.json` contract (version 0.1.0)

The project writes this file beside its outputs. `run_date_utc` is the current run. Every step has `elapsed_seconds`, `peak_rss_mb`, `rss_basis` (`process` or `tree`), `measurement_run_date_utc`, and `skipped` (true or false). When `skipped` is true, the project keeps that step's last measured time, memory, basis, and date; `carry_forward_skipped_steps` can do this. `outputs` lists each made file and its full SHA-256 hash. The code version comes from `manifest.json`, so it is not repeated here.

```json
{
  "schema_version": "0.1.0",
  "run_date_utc": "2026-11-03T12:00:00Z",
  "steps": [{
    "name": "read",
    "elapsed_seconds": 38,
    "peak_rss_mb": 900,
    "rss_basis": "tree",
    "measurement_run_date_utc": "2026-11-03T12:00:00Z",
    "skipped": false
  }],
  "outputs": [{
    "path": "panel.csv",
    "sha256": "3440a3cda52993122c8d0b26440b6c239c05d00273652a6df17932c580407642"
  }]
}
```

## Acceptance evidence

- Automated: a synthetic fixture project runs the quick check offline, verifies its output, and renders a run summary. Missing measurements and stale hashes fail clearly. Template CI runs on Windows and Linux after `uv sync --locked` and limits the quick check to 60 seconds.
- Human check: Aaron ran the generated README commands as a newcomer. The commands worked; his wording feedback was incorporated and approved in c62fe00.

## Release dependency

The generated template pins the reprokit v0.3.1 tag.
