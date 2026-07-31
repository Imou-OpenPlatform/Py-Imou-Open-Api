# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed

- PaaS siren: IPC devices omit channel params; non-IPC devices use `channels` array instead of `channelId`
- IoT SirenStart `clientLocalTime` format corrected to `yyyyMMdd'T'HHmmss`
- Collection point placeholder state key renamed to `select_collection_point` (Hassfest-compatible)

## [1.3.3]

### Added

- Collection point (PTZ preset) support: `getCollection` / `turnCollection` PaaS APIs and IoT `GetCollection` / `TurnCollection` services
- `ImouDeviceManager.async_get_device_collection()` / `async_turn_device_collection()`
- `pyimouapi.collection_point` — parse PaaS / IoT preset name lists; `build_collection_point_options()` for select UIs
- `select.collection_point` on `ImouHaDevice` when the device has `CollectionPoint` ability or IoT refs `21500`/`22000` (placeholder current option; preset order preserved from API)
- Siren start/stop button support: PaaS `sirenStart`/`sirenStop` and IoT refs `25500`/`22200`
- `ImouDeviceManager.async_siren_start()` / `async_siren_stop()`
- `pyimouapi.siren` — `client_local_time_iso()` and `build_siren_start_iot_content()` for IoT SirenStart

### Changed

- IoT collection point refresh reuses `_get_state_from_properties_or_services` (same path as other service reads)
- Select/switch writes update local entity state optimistically; no post-write cloud read (IoT switch ref path no longer sleeps and re-queries properties)

## [1.3.2]

### Fixed

- Compare `channelId` as string when matching online status and abilityRefs maps
- Guard empty `deviceList` in `async_get_iot_device_properties`
- Honor `value_type=str` when setting IoT text properties
- Add `async_close` on device managers to close the Open API session

## [1.3.1]

### Added

- `ImouDeviceManager.async_ensure_event_map` / `async_resolve_event_identifier` for lazy `getProductModel` event ref→identifier caching

## [1.3.0]

### Changed

- Sensor `PARAM_STATE` values are normalized to `int`/`float` for numeric sensors.
- Added `PARAM_STATE_VARIANT` (`numeric` | `enum`) on sensor entries.
- Added `pyimouapi.sensor.normalize_sensor_state` and `apply_sensor_state`.

## 1.2.9

### Added

- `async_set_message_callback` on `ImouOpenApiClient` to register or unregister Imou Open Platform message callbacks.
- `ImouDeviceSummary` dataclass and `async_get_device_summaries` on `ImouDeviceManager` for lightweight paginated device listing.

## 1.2.8

### Changed

- Device status polling uses a single `getIotDeviceDetailInfo` call to read all IoT property refs instead of one `getIotDeviceProperties` call per entity.
- Post-operation single-ref refresh still uses `getIotDeviceProperties` to keep post-write queries lightweight.
- Expanded `pyproject.toml` for dev tooling; `setup.py` reads README via `Path.read_text`.

### Added

- Debug logs when a property ref is missing in `getIotDeviceDetailInfo` or `getIotDeviceProperties` responses.
- CI workflows (lint, spell, YAML, version-sync, test), contribution docs, and local dev scripts aligned with Imou-Home-Assistant governance.
- Unit tests for property lookup and detail-based device status updates.
