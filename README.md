# pyimouapi

Async Python client for the **Imou Open Platform** cloud APIs. Built on **aiohttp**, it handles authentication and requests, and exposes device helpers plus higher-level types for integrations (for example Home Assistant **Imou Life 2.0**).

- **Repository:** [Imou-OpenPlatform/Py-Imou-Open-Api](https://github.com/Imou-OpenPlatform/Py-Imou-Open-Api)
- **Version:** Same as `pyproject.toml` / PyPI (`pyimouapi.__version__`) — **2.0.1** on the `dev` / release line that ships with Imou Life 2.0
- **Python:** `>= 3.11`

## What 2.0 does

Entity registration and control use Open API **V2** capability ids from the device list, intersected with packaged `v2_target_map.yaml`. `device.capability.list` enriches enums, ranges, and scopes for selected devices. Select options use stable friendly keys (`select_option`), including night-vision `starlight` ↔ raw `"5"` and five-level volume `"1"`–`"5"`.

## Package layout

| Module | Role |
|--------|------|
| `pyimouapi.openapi` | `ImouOpenApiClient` — auth, signing, token lifecycle, HTTP calls |
| `pyimouapi.device` | `ImouDeviceManager`, `ImouDevice`, `ImouChannel` — listing and related endpoints |
| `pyimouapi.capability` | V2 capability list / property / service clients and `configure_imou_ha_device_from_capability` |
| `pyimouapi.data` | Packaged `v2_target_map.yaml` (`ha_key` → V2 `target_id`) |
| `pyimouapi.ha_device` | `ImouHaDeviceManager`, `ImouHaDevice` — aggregated device model for automation stacks |
| `pyimouapi.select_option` | Friendly keys for `device_volume`, `night_vision_mode`, `wide_dynamic` |
| `pyimouapi.alarm_mode` | Alarm panel mode friendly ↔ raw mapping |
| `pyimouapi.push` | Event-push helpers: normalize fields, alarm vs status, IoT envelopes, picture URLs |
| `pyimouapi.pic_decode` | `LCOpenPicDecoder` — decrypts alarm pictures you already downloaded (official LCOpenSDK `.so`, linux x86-64) |
| `pyimouapi.play_token` | Play-token / encrypt-key helpers for picture decrypt |
| `pyimouapi.cloud_record` / `local_record` | Cloud and local recording listing |
| `pyimouapi.playback` | HLS / FLV playback URL helpers |
| `pyimouapi.insight` | AI Insight cloud status, alarm search, daily statistics |
| `pyimouapi.snap_detect` | `detectDeviceSnap` / `deviceSnapDetect` client and result parsing |
| `pyimouapi.bulb_light` | Color-bulb composite property writes |
| `pyimouapi.collection_point` | Collection-point name parsing |
| `pyimouapi.exceptions` | `ImouException` and typed errors |

The top-level `pyimouapi` package re-exports common symbols. Import submodules directly when needed, for example `from pyimouapi.ha_device import ImouHaDeviceManager`.

## Dependencies

As declared in `pyproject.toml` / `requirements.txt`:

- `aiohttp>=3.11.9,<4.0`

## Install

```bash
pip install pyimouapi
```

From a checkout:

```bash
pip install .
```

## Quick example (async)

```python
from pyimouapi.openapi import ImouOpenApiClient

# host: Imou Open Platform gateway, e.g. openapi-sg.easy4ip.com
client = ImouOpenApiClient("your_app_id", "your_app_secret", "openapi-sg.easy4ip.com")
await client.async_get_token()
# Use the client with pyimouapi.ha_device.ImouHaDeviceManager for integrations
```

## License

MIT — see `LICENSE` in this repository.
