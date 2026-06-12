# Changelog

All notable changes to this project will be documented in this file.

## 1.2.8

### Changed

- Device status polling uses a single `getIotDeviceDetailInfo` call to read all IoT property refs instead of one `getIotDeviceProperties` call per entity.
- Post-operation single-ref refresh still uses `getIotDeviceProperties` to keep post-write queries lightweight.
- Expanded `pyproject.toml` for dev tooling; `setup.py` reads README via `Path.read_text`.

### Added

- Debug logs when a property ref is missing in `getIotDeviceDetailInfo` or `getIotDeviceProperties` responses.
- CI workflows (lint, spell, YAML, version-sync, test), contribution docs, and local dev scripts aligned with Imou-Home-Assistant governance.
- Unit tests for property lookup and detail-based device status updates.
