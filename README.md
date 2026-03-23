# UP Chime PoE LED Tool

Control the UP Chime PoE LED with `set_chime_led.py`.

## Requirements

- `python3`
- `sshpass`
- Network access to the NVR
- SSH access for the configured NVR account
- UniFi Protect running
- The Protect Node inspector available on `127.0.0.1:9229`

## Setup

```bash
cp chime_tool_config.example.json chime_tool_config.local.json
```

Fill in `chime_tool_config.local.json`:

- `nvr_host`
- `nvr_user`
- `nvr_password`
- `chime_mac`

`chime_tool_config.local.json` is gitignored.

Optional environment overrides:

- `CHIME_NVR_HOST`
- `CHIME_NVR_USER`
- `CHIME_NVR_PASSWORD`
- `CHIME_CHIME_MAC`
- `CHIME_NODE_BINARY`
- `CHIME_INSPECTOR_WS_URL`
- `CHIME_DEVICE_CONNECTION_MODULE_ID`

## Usage

```bash
python3 set_chime_led.py off
python3 set_chime_led.py on
python3 set_chime_led.py off --config /path/to/chime_tool_config.local.json
```

On success, the script prints JSON such as:

```json
{"ok":true,"requestedState":"off","response":{"errorCode":0,"body":{"status":"ok"}}}
```

## Troubleshooting

- `Missing required config value`: check the config file or environment variables
- `sshpass: command not found`: install `sshpass`
- SSH timeout or authentication failure: verify `nvr_host`, `nvr_user`, and `nvr_password`
- `Could not discover a Node.js binary on the NVR`: set `CHIME_NODE_BINARY`
- `Could not discover the inspector WebSocket URL`: confirm Protect is running and the inspector is available
- `chime connection not found`: verify `chime_mac`
