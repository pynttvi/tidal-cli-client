from __future__ import annotations

import json
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class MPVPlayer:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._socket_path = Path(tempfile.gettempdir()) / "tidal-cli-client-mpv.sock"
        self._current_url: str | None = None

    @property
    def current_url(self) -> str | None:
        return self._current_url

    @property
    def is_playing(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def play(self, url: str) -> None:
        self.stop()
        self._current_url = url
        try:
            if self._socket_path.exists():
                self._socket_path.unlink()
        except OSError:
            pass

        self._process = subprocess.Popen(
            [
                "mpv",
                "--no-video",
                "--really-quiet",
                f"--input-ipc-server={self._socket_path}",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _send_ipc(self, command: list[object]) -> bool:
        if not self._socket_path.exists() or not self.is_playing:
            return False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(self._socket_path))
                client.sendall((json.dumps({"command": command}) + "\n").encode("utf-8"))
            return True
        except OSError:
            return False

    def _request_ipc(self, command: list[object]) -> Any | None:
        if not self._socket_path.exists() or not self.is_playing:
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.25)
                client.connect(str(self._socket_path))
                client.sendall((json.dumps({"command": command}) + "\n").encode("utf-8"))
                response = client.recv(4096).decode("utf-8").strip()
            if not response:
                return None
            payload = json.loads(response)
            if payload.get("error") != "success":
                return None
            return payload.get("data")
        except (OSError, TimeoutError, json.JSONDecodeError):
            return None

    def get_time_position(self) -> float | None:
        time_position = self._request_ipc(["get_property", "time-pos"])
        if isinstance(time_position, (int, float)):
            return float(time_position)
        return None

    @property
    def is_paused(self) -> bool:
        pause_state = self._request_ipc(["get_property", "pause"])
        return pause_state is True

    def pause(self) -> None:
        self._send_ipc(["set_property", "pause", True])

    def resume(self) -> None:
        self._send_ipc(["set_property", "pause", False])

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._send_ipc(["quit"])
            self._process.terminate()
            try:
                self._process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._current_url = None
        try:
            if self._socket_path.exists():
                self._socket_path.unlink()
        except OSError:
            pass

    def finished(self) -> bool:
        return self._process is not None and self._process.poll() is not None

    def __del__(self) -> None:
        self.stop()
