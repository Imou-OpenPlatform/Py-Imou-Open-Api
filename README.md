# pyimouapi

Async Python client for the **Imou Open Platform** cloud APIs. Built on **aiohttp**, it handles authentication and requests, and exposes device/channel helpers plus higher-level types for integrations (for example Home Assistant).

- **Repository:** [Imou-OpenPlatform/Py-Imou-Open-Api](https://github.com/Imou-OpenPlatform/Py-Imou-Open-Api)
- **Version:** Same as `setup.py` / PyPI (`pyimouapi.__version__`)
- **Python:** `>= 3.11`

## Package layout

| Module | Role |
|--------|------|
| `pyimouapi.openapi` | `ImouOpenApiClient` — auth, signing, token lifecycle, HTTP calls |
| `pyimouapi.device` | `ImouDeviceManager`, `ImouDevice`, `ImouChannel` — listing, PTZ, alarms, storage, and related endpoints |
| `pyimouapi.ha_device` | `ImouHaDeviceManager`, `ImouHaDevice`, … — aggregated “device model” helpers for automation stacks |
| `pyimouapi.exceptions` | `ImouException` and typed errors (connect, request, invalid credentials, …) |

The top-level `pyimouapi` package re-exports common symbols. Import submodules directly when needed, for example `from pyimouapi.ha_device import ImouHaDeviceManager`.

## Dependencies

As declared in `setup.py` / `requirements.txt`:

- `aiohttp>=3.11.9,<4.0`
- `simpleeval>=1.0.3`

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
# Use the client with pyimouapi.device.ImouDeviceManager for device operations
```

## License

MIT — see `LICENSE` in this repository.
