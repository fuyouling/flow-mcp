"""Browser launcher configuration loader and flags parser."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

# pyrefly: ignore [untyped-import]
import yaml
from loguru import logger

from flow_mcp.config import get_settings


def _expand_env_vars(text: str, env_vars: Mapping[str, str] | None = None) -> str:
    """Expand environment variables in text supporting ${VAR} and $VAR formats."""
    merged: dict[str, str] = dict(os.environ)
    if env_vars:
        for k, v in env_vars.items():
            if v is not None:
                # pyrefly: ignore [unnecessary-type-conversion]
                merged[k] = str(v)

    def _sub(m: re.Match) -> str:
        var_name = m.group(1) or m.group(2)
        return str(merged.get(var_name, m.group(0)))

    return re.sub(r"\$\{([A-Za-z0-9_]+)\}|\$([A-Za-z0-9_]+)", _sub, text)


def load_browser_flags(
    config_path: str | None = None,
    env_vars: Mapping[str, str] | None = None,
) -> list[str]:
    """Load browser launch flags from YAML configuration file."""
    if config_path is None:
        config_path = get_settings().browser_config_path

    path = Path(config_path)
    if not path.exists():
        logger.debug(f"browser config does not exist: {path}, using default flags")
        return []

    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to parse browser configuration {path}: {e}")
        return []

    if not data or not isinstance(data, dict):
        return []

    flags: list[str] = []

    # Support format 1: 'flags: ["--disable-gpu", ...]'
    if "flags" in data and isinstance(data["flags"], list):
        for flag in data["flags"]:
            if isinstance(flag, str):
                expanded = _expand_env_vars(flag, env_vars)
                flags.append(expanded)

    # Support format 2: 'browser: [{"flag": "--flag", "enabled": True}, ...]'
    if "browser" in data and isinstance(data["browser"], list):
        for entry in data["browser"]:
            if isinstance(entry, dict) and entry.get("enabled", True):
                raw_flag = entry.get("flag", "")
                if raw_flag:
                    expanded = _expand_env_vars(raw_flag, env_vars)
                    flags.append(expanded)

    return flags


def get_browser_port(config_path: str | None = None) -> int:
    """Extract remote debugging port from browser_config.yaml or fallback to 9222."""
    if config_path is None:
        config_path = get_settings().browser_config_path

    path = Path(config_path)
    if not path.exists():
        return 9222

    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return 9222

    if not data or not isinstance(data, dict):
        return 9222

    if "remote_debugging_port" in data:
        try:
            return int(data["remote_debugging_port"])
        except ValueError:
            pass

    for entry in data.get("browser", []):
        if isinstance(entry, dict) and entry.get("enabled", True):
            flag = entry.get("flag", "")
            if flag.startswith("--remote-debugging-port="):
                try:
                    return int(flag.split("=", 1)[1])
                except ValueError:
                    pass

    return 9222
