# UP Chime PoE LED Tools

This repo now keeps a small supported toolset for working with the UP Chime PoE LED through a live UniFi Protect process.

## Supported script

- `set_chime_led.py`
  - Sends the verified payload `{state: "off"}` or `{state: "on"}` through Protect's live `DeviceConnection`

The firmware/reverse-engineering notes remain in `UP_Chime_PoE_LED_Analysis.md`.

## Local configuration

Copy the example config and fill in your local values:

```bash
cp chime_tool_config.example.json chime_tool_config.local.json
```

Required fields:

- `nvr_host`
- `nvr_user`
- `nvr_password`
- `chime_mac`

Automatically detected at runtime:

- Protect Node binary on the NVR
- Active inspector WebSocket URL from `http://127.0.0.1:9229/json`
- Webpack `DeviceConnection` module id

The local config file is gitignored.

You can also override any value with environment variables:

- `CHIME_NVR_HOST`
- `CHIME_NVR_USER`
- `CHIME_NVR_PASSWORD`
- `CHIME_CHIME_MAC`

Optional overrides exist for the auto-detected values if needed:

- `CHIME_NODE_BINARY`
- `CHIME_INSPECTOR_WS_URL`
- `CHIME_DEVICE_CONNECTION_MODULE_ID`

## Usage

Turn the LED off:

```bash
python3 set_chime_led.py off
```

Turn the LED on:

```bash
python3 set_chime_led.py on
```

Use an explicit config file path:

```bash
python3 set_chime_led.py off --config /path/to/chime_tool_config.local.json
```

## Notes

- These scripts rely on a live Node inspector connection to the Protect process.
- The currently verified payload shape is `{state: "off"}` / `{state: "on"}`.
- The cleanup intentionally removed the one-off probe and attack scripts that previously held inline credentials and duplicated logic.
