#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG_PATH = Path(__file__).resolve().with_name("chime_tool_config.local.json")


@dataclass(frozen=True)
class ChimeToolConfig:
    nvr_host: str
    nvr_user: str
    nvr_password: str
    node_binary: Optional[str]
    inspector_ws_url: Optional[str]
    chime_mac: str
    device_connection_module_id: Optional[int] = None


def _read_json_file(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text())


def load_config(config_path: str | None = None) -> ChimeToolConfig:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    file_values = _read_json_file(path)

    def get_value(file_key: str, env_key: str, default: str | None = None) -> str:
        value = os.environ.get(env_key, file_values.get(file_key, default))
        if value is None or value == "":
            raise ValueError(
                f"Missing required config value '{file_key}'. "
                f"Set {env_key} or add it to {path}."
            )
        return str(value)

    def get_int_value(file_key: str, env_key: str, default: int) -> int:
        value = os.environ.get(env_key, file_values.get(file_key, default))
        return int(value)

    def get_optional_value(file_key: str, env_key: str) -> str | None:
        value = os.environ.get(env_key, file_values.get(file_key))
        if value in (None, ""):
            return None
        return str(value)

    def get_optional_int_value(file_key: str, env_key: str) -> int | None:
        value = os.environ.get(env_key, file_values.get(file_key))
        if value in (None, ""):
            return None
        return int(value)

    return ChimeToolConfig(
        nvr_host=get_value("nvr_host", "CHIME_NVR_HOST"),
        nvr_user=get_value("nvr_user", "CHIME_NVR_USER", "root"),
        nvr_password=get_value("nvr_password", "CHIME_NVR_PASSWORD"),
        node_binary=get_optional_value("node_binary", "CHIME_NODE_BINARY"),
        inspector_ws_url=get_optional_value("inspector_ws_url", "CHIME_INSPECTOR_WS_URL"),
        chime_mac=get_value("chime_mac", "CHIME_CHIME_MAC"),
        device_connection_module_id=get_optional_int_value(
            "device_connection_module_id",
            "CHIME_DEVICE_CONNECTION_MODULE_ID",
        ),
    )