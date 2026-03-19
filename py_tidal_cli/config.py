from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".config" / "tidal-cli-client"
APP_CONFIG_PATH = CONFIG_DIR / "app.json"


DEFAULT_APP_CONFIG: dict[str, Any] = {
    "INPUT_BAR_ACTIONS": {
        "PAUSE": "pause",
        "RESUME": "resume",
        "PLAYLISTS": "playlists",
        "QUEUE": "queue",
        "NEXT": "next",
        "SKIP": "skip",
        "SHUFFLE": "shuffle",
        "QUIT": "quit",
        "SEARCH": "search",
    },
    "SHORTCUTS": {
        "LIST_DOWN": "k",
        "LIST_UP": "j",
        "OPEN_INPUT_BAR": ":",
        "PLAY_NEXT_TRACK": "l",
    },
}


@dataclass
class AppConfig:
    data: dict[str, Any]

    @property
    def input_actions(self) -> dict[str, str]:
        return self.data.get("INPUT_BAR_ACTIONS", DEFAULT_APP_CONFIG["INPUT_BAR_ACTIONS"])


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_json_with_default(path: Path, default_data: dict[str, Any]) -> dict[str, Any]:
    _ensure_parent(path)
    if not path.exists():
        path.write_text(json.dumps(default_data, indent=2), encoding="utf-8")
        return dict(default_data)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            merged = dict(default_data)
            for key, value in raw.items():
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged[key] = {**merged[key], **value}
                else:
                    merged[key] = value
            return merged
    except json.JSONDecodeError:
        pass

    path.write_text(json.dumps(default_data, indent=2), encoding="utf-8")
    return dict(default_data)


def load_app_config() -> AppConfig:
    return AppConfig(_load_json_with_default(APP_CONFIG_PATH, DEFAULT_APP_CONFIG))
