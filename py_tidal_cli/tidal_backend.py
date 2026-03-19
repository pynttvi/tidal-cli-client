from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SearchResult:
    id: str
    title: str
    subtitle: str
    raw: Any
    kind: str


class TidalBackend:
    def __init__(self) -> None:
        import tidalapi

        self._tidalapi = tidalapi
        self.session = tidalapi.Session()
        self._is_logged_in = False
        self._session_notice: str | None = None
        self._session_dir = Path.home() / ".config" / "tidal-cli-client"
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._oauth_session_path = self._session_dir / "oauth-session.json"

    def pop_session_notice(self) -> str | None:
        notice = self._session_notice
        self._session_notice = None
        return notice

    def _session_has_auth(self) -> bool:
        return bool(
            getattr(self.session, "access_token", None)
            or getattr(self.session, "session_id", None)
            or getattr(self.session, "user", None)
        )

    def _refresh_session_if_needed(self) -> bool:
        expiry_time = getattr(self.session, "expiry_time", None)
        refresh_token = getattr(self.session, "refresh_token", None)
        token_refresh = getattr(self.session, "token_refresh", None)

        if not isinstance(expiry_time, datetime.datetime):
            return self._session_has_auth()
        if not refresh_token or not callable(token_refresh):
            return self._session_has_auth()

        now = datetime.datetime.now(tz=expiry_time.tzinfo)
        if now + datetime.timedelta(seconds=60) < expiry_time:
            return self._session_has_auth()

        refreshed = bool(token_refresh(refresh_token))
        if refreshed:
            self._save_persisted_session()
            self._session_notice = "Session refreshed"
        return refreshed and self._session_has_auth()

    def _ensure_active_session(self) -> bool:
        if not self._session_has_auth():
            return False
        return self._refresh_session_if_needed()

    def _save_persisted_session(self) -> None:
        try:
            if hasattr(self.session, "save_session_to_file"):
                self.session.save_session_to_file(self._oauth_session_path)
                return

            payload = {
                "token_type": getattr(self.session, "token_type", None),
                "access_token": getattr(self.session, "access_token", None),
                "refresh_token": getattr(self.session, "refresh_token", None),
                "expiry_time": None,
                "is_pkce": bool(getattr(self.session, "is_pkce", False)),
            }
            expiry_time = getattr(self.session, "expiry_time", None)
            if isinstance(expiry_time, datetime.datetime):
                payload["expiry_time"] = expiry_time.isoformat()

            self._oauth_session_path.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception:
            # Failing to persist tokens should not break runtime playback.
            return

    def _load_persisted_session(self) -> bool:
        if not self._oauth_session_path.exists():
            return False

        try:
            if hasattr(self.session, "load_session_from_file"):
                return bool(
                    self.session.load_session_from_file(self._oauth_session_path)
                )
        except Exception:
            pass

        if not hasattr(self.session, "load_oauth_session"):
            return False

        try:
            payload = json.loads(self._oauth_session_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return False

            token_type = payload.get("token_type")
            access_token = payload.get("access_token")
            refresh_token = payload.get("refresh_token")
            expiry_time_raw = payload.get("expiry_time")
            is_pkce = bool(payload.get("is_pkce", False))

            if not token_type or not access_token:
                return False

            expiry_time = None
            if isinstance(expiry_time_raw, str) and expiry_time_raw:
                try:
                    expiry_time = datetime.datetime.fromisoformat(expiry_time_raw)
                except ValueError:
                    expiry_time = None

            return bool(
                self.session.load_oauth_session(
                    token_type=token_type,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expiry_time=expiry_time,
                    is_pkce=is_pkce,
                )
            )
        except Exception:
            return False

    @property
    def is_logged_in(self) -> bool:
        return self._is_logged_in

    def login(self) -> bool:
        if self._load_persisted_session():
            self._is_logged_in = self._ensure_active_session()
            return self._is_logged_in

        if hasattr(self.session, "login_oauth_simple"):
            self.session.login_oauth_simple()
            self._is_logged_in = self._session_has_auth()
            self._save_persisted_session()
            return self._is_logged_in

        return False

    def _search_model(self, kind: str) -> Any:
        mapping = {
            "tracks": getattr(self._tidalapi, "Track", None),
            "artists": getattr(self._tidalapi, "Artist", None),
            "albums": getattr(self._tidalapi, "Album", None),
            "playlists": getattr(self._tidalapi, "Playlist", None),
        }
        return mapping.get(kind) or getattr(self._tidalapi, "Track")

    def search(
        self, query: str, kind: str = "tracks", limit: int = 20
    ) -> list[SearchResult]:
        if not self._ensure_active_session():
            raise RuntimeError("Not authenticated with TIDAL")
        model = self._search_model(kind)
        found = self.session.search(query, models=[model], limit=limit)

        if isinstance(found, dict):
            key = kind
            bucket = found.get(key, [])
            if not bucket and key.endswith("s"):
                bucket = found.get(key[:-1], [])
        else:
            bucket = list(found)

        return [self._to_search_result(item) for item in bucket]

    def _to_search_result(self, item: Any) -> SearchResult:
        kind = item.__class__.__name__.lower() + "s"
        item_id = str(getattr(item, "id", getattr(item, "uuid", "")))
        title = getattr(item, "name", None) or getattr(item, "title", None) or item_id

        subtitle = ""
        if kind == "tracks":
            artist_name = getattr(getattr(item, "artist", None), "name", "")
            album_name = getattr(getattr(item, "album", None), "name", "")
            subtitle = " - ".join([x for x in [artist_name, album_name] if x])
        elif kind == "albums":
            subtitle = getattr(getattr(item, "artist", None), "name", "")
        elif kind == "playlists":
            subtitle = getattr(item, "description", "") or "playlist"

        return SearchResult(
            id=item_id,
            title=str(title),
            subtitle=str(subtitle),
            raw=item,
            kind=kind,
        )

    def get_user_playlists(self) -> list[SearchResult]:
        if not self._ensure_active_session():
            raise RuntimeError("Not authenticated with TIDAL")
        user = self.session.user
        if user is None:
            return []
        playlists = user.playlists()
        return [self._to_search_result(x) for x in playlists]

    def list_tracks_from_result(self, result: SearchResult) -> list[SearchResult]:
        if not self._ensure_active_session():
            raise RuntimeError("Not authenticated with TIDAL")
        raw = result.raw
        kind = result.kind

        if kind == "tracks":
            return [result]
        if kind == "albums" and hasattr(raw, "tracks"):
            return [self._to_search_result(x) for x in raw.tracks()]
        if kind == "artists":
            tracks = []
            if hasattr(raw, "get_top_tracks"):
                tracks = raw.get_top_tracks()
            elif hasattr(raw, "top_tracks"):
                tracks = raw.top_tracks()
            return [self._to_search_result(x) for x in tracks]
        if kind == "playlists" and hasattr(raw, "tracks"):
            return [self._to_search_result(x) for x in raw.tracks()]
        return []

    def get_track_stream_url(self, track_result: SearchResult) -> str:
        if not self._ensure_active_session():
            raise RuntimeError("Not authenticated with TIDAL")
        track = track_result.raw

        for method_name in ("get_url", "get_stream_url"):
            method = getattr(track, method_name, None)
            if callable(method):
                value = method()
                if isinstance(value, str) and value:
                    return value
                candidate = getattr(value, "url", None)
                if isinstance(candidate, str) and candidate:
                    return candidate

        stream_method = getattr(track, "get_stream", None)
        if callable(stream_method):
            stream_obj = stream_method()
            candidate = getattr(stream_obj, "url", None)
            if isinstance(candidate, str) and candidate:
                return candidate

        raise RuntimeError("Could not resolve stream URL for selected track")
