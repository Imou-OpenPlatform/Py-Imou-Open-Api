# Changelog

All notable changes to this project will be documented in this file.

## [1.3.5]

Supersedes the unreleased 1.3.4.1. Nothing was removed from the public API, so
this is a drop-in replacement for 1.3.4.

### Breaking

- The `motion_detect` switch is no longer offered for product_id `FKX9UYL4`. That model advertises refs `14800` and `305000` but cannot serve them, so the entity never worked; consumers that had one will see it disappear
- `async_get_device_image()` raises the reason a snapshot failed instead of logging it and returning `None`, so a caller can put it in front of a user
- A 5xx response raises `ConnectFailedException` rather than `RequestFailedException`. Callers separating "could not reach the service" from "the request was refused" get the former for gateway and outage responses
- Writing a switch that resolves to no ability raises instead of reporting the write as done
- A refused `appId` / `appSecret` now propagates out of `async_update_device_status()` instead of being logged as a failed read. Callers that treated a status update as never raising will start seeing `InvalidAppIdOrSecretException`, which is what lets them prompt for new credentials; every other read failure is still logged and skipped as before

### Security

- Debug logging no longer prints the request signature, `token`, or `accessToken`. Turning on debug logs used to write live credentials into the Home Assistant log, which is included verbatim in the diagnostics users attach to bug reports

### Added

- `ImouDeviceManager.async_bind_device()` — OpenAPI `bindDevice` (device serial + verification code)
- `ImouOpenApiClient.async_download()` and `ImouDeviceManager.async_download()` — snapshot downloads now go through the client's shared session instead of a throwaway one
- `compose_iot_device_id()` — the one place that builds an accessory's composite device id
- A `py.typed` marker, so consumers type check against the annotations shipped here

### Changed

- Concurrent callers asking for an `accessToken` are coalesced behind a lock into a single request, and a token expiring mid-flight is retried once rather than in a loop
- Listing devices resolves every iot device's ability refs in one concurrent batch instead of one round trip after another
- Service-backed sensors and texts refresh together, as do the switches, selects, and sensors of a single device. A camera carrying a dozen switches no longer spends a dozen sequential requests per poll
- One HTTP session is shared across the client with a capped connection pool
- Status read failures are logged instead of being gathered and silently dropped; cancellation is passed through rather than reported as a failure
- A sleeping device is logged at debug, not info — battery cameras were writing an info line on every poll for as long as they slept
- Log messages are left for the logger to format, so a disabled level costs nothing
- Ref-based entity setup for all six platforms is driven by one table registry rather than six near-identical functions

### Fixed

- IoT `motion_detect`: skip advertised but unusable refs `14800` and `305000` for product_id `FKX9UYL4` (falls through to `108800`); log at debug when an `excepts` entry skips a matching ref
- Paging stops on a short page rather than on the `count` field. Read as an account total, `count` sent an account holding an exact multiple of the page size asking for pages forever
- A connection is released when a response body fails to read, and when a snapshot download returns a non-200 status. Both used to strand the connection in the pool
- A non-200 response is reported as a request failure carrying the status code. Parsing an error page as JSON used to surface a gateway error as a connection problem
- A failed switch read no longer reads as the switch being on. The gathered exception was an object, and every object is truthy
- Writing a switch that resolves to no abilities no longer raises `IndexError`
- An accessory is addressed with its composite id only when both parent ids are known; a missing parent id used to raise `TypeError` and take down the whole device listing
- The connection cap is per host rather than total. Snapshots are fetched from storage and allowed a far longer budget, so a few of them held every slot in the shared pool while API calls queued past their own deadline and were reported as connection failures
- Listing an account survives one accessory that cannot be read. That device keeps its placeholder refs and is retried by the next listing, instead of costing the caller every other device for as long as it stays unhappy
- Downloads report a network failure as `ConnectFailedException` instead of letting a raw `aiohttp` error escape
- Annotations the package promises its callers are correct, and the type checker runs in CI to keep them that way. The `delegate` property had no return type, which hid fourteen real mismatches from the checker
- Revoked credentials are reported rather than logged. Every read handler swallowed them, so a consumer polling status could not tell a rotated secret from a quiet device and went on showing stale values as current

### Changed

- Text writes update local entity state optimistically; countdown text no longer sleeps and re-queries after write
- Select `current_option` / `options` for `mode`, `device_volume`, and `night_vision_mode` use stable friendly keys (`home`/`away`/`disarm`, `mute`/`low`/`medium`/`high`, `intelligent`/`fullcolor`/…); IoT numeric codes are mapped at the library boundary (breaking for consumers that compared numeric option strings)

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
