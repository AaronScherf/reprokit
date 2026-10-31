# Changelog

All notable changes to this project are documented here. Format follows Keep a Changelog; versions follow SemVer.

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
