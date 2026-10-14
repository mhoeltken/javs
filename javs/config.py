# SPDX-License-Identifier: Apache-2.0
"""JAVS configuration: the polling level in ~/.config/javs/config.json."""

import json
import os

POLL_INTERVALS_MS = {"tight": 2000, "medium": 5000, "relaxed": 15000}
DEFAULT_POLL = "medium"


def default_config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return os.path.join(base, "javs", "config.json")


def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_poll(path):
    poll = _read(path).get("poll")
    if isinstance(poll, str) and poll in POLL_INTERVALS_MS:
        return poll
    return DEFAULT_POLL


def save_poll(path, poll):
    if poll not in POLL_INTERVALS_MS:
        raise ValueError(f"Unknown poll level: {poll!r}")
    data = _read(path)
    data["poll"] = poll
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(tmp_path, path)
