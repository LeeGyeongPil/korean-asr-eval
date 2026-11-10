# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-11-11

### Fixed
- `score` and `compare` accept `--ref-encoding` and `--hyp-encoding`, so a cp949 reference can be scored against UTF-8 hypotheses; `--encoding` still applies to both. Decoding errors now name the real CLI options.

## [0.1.0] - 2026-11-10

### Added
- Normalization profiles with an id (`name@version`) and a 12-hex fingerprint: `none@1`, `basic@1`, `kspon-spelling@1`, `kspon-phonetic@1`.
- User profiles from TOML (`extends`, `[replace]`, `[[steps]]`).
- `normalize`, `normalize_trace`, `score` (CER micro/macro, CER without spaces, WER, S/D/I, empty-reference policy), `compare` (per-profile ranks, percentage-point deltas, rank flips, most-changed utterances), `to_jiwer_transform`.
- Readers for `tsv`, `jsonl`, `trn` and `txt` files with id matching (`IdMismatchError`).
- CLI: `profiles`, `normalize`, `score`, `compare`, `demo`; JSON output is byte-stable.
- Bundled hand-written practice sample (not real model output) for the offline `demo`.
