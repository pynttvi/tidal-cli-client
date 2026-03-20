from __future__ import annotations

import curses
import locale
import shutil
import textwrap
import traceback
from collections import deque
from dataclasses import dataclass, field

from .config import load_app_config
from .player import MPVPlayer
from .tidal_backend import SearchResult, TidalBackend


HELP_TEXT = (
    "Commands: search <query> | search <type> <query> (track/album/artist/playlist also work) | playlists | queue | pause | resume | "
    "next | skip <n> | shuffle | home | quit | g=home | u=my playlists | p=play+queue album/playlist | Enter=open/play | Backspace=back"
)


@dataclass
class UIState:
    status: str = "Starting"
    current_track: SearchResult | None = None
    current_view: str = "home"
    command: str = ""
    list_items: list[SearchResult] = field(default_factory=list)
    selected_index: int = 0
    queue: deque[SearchResult] = field(default_factory=deque)
    entering_command: bool = False


class CursesTidalApp:
    def __init__(self) -> None:
        self.config = load_app_config()
        self.backend = TidalBackend()
        self.player = MPVPlayer()
        self.state = UIState(status="Login required")
        self.running = True
        self.view_stack: list[tuple[str, list[SearchResult], int, str]] = []

    def _configure_screen(self, stdscr: curses.window) -> None:
        if not curses.has_colors():
            return

        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            return

        stdscr.bkgd(" ", curses.color_pair(0))

    def _apply_backend_notice_to_status(self) -> None:
        notice = self.backend.pop_session_notice()
        if not notice:
            return
        if self.state.status:
            self.state.status = f"{self.state.status} | {notice}"
        else:
            self.state.status = notice

    def ensure_logged_in(self) -> None:
        ok = self.backend.login()
        if not ok:
            raise RuntimeError(
                "TIDAL OAuth login failed. Ensure your tidalapi OAuth flow can complete in this environment."
            )

        self.state.status = "Signed in"

    def _safe_addnstr(
        self,
        stdscr: curses.window,
        y: int,
        x: int,
        text: str,
        max_width: int,
        attr: int = curses.A_NORMAL,
    ) -> None:
        """Safely add a string to curses window with UTF-8 support.

        Uses addstr() instead of addnstr() to properly handle UTF-8 multi-byte characters.
        """
        try:
            # Check if the position is valid
            height, width = stdscr.getmaxyx()
            if y < 0 or y >= height or x < 0 or x >= width:
                return

            # Truncate string to fit within the window
            # Keep it simple - just truncate the string if it's too long
            if len(text) > max_width:
                text = text[:max_width]

            # Use addstr() which properly handles UTF-8
            # Move to position and add the string with attribute
            try:
                stdscr.addstr(y, x, text, attr)
            except curses.error:
                # If that fails, try without attribute
                try:
                    stdscr.addstr(y, x, text)
                except Exception:
                    # Give up silently
                    pass
        except Exception:
            # Silently ignore any errors
            pass

    def draw(self, stdscr: curses.window) -> None:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        title = "tidal-cli-client (Python curses port)"
        now_playing = "No track"
        if self.state.current_track is not None:
            now_playing = f"{self.state.current_track.title}"

        header = f"{title} | Status: {self.state.status} | Playing: {now_playing}"
        self._safe_addnstr(stdscr, 0, 0, header, width - 1, curses.A_BOLD)
        stdscr.hline(1, 0, ord("-"), width)

        footer_lines = self._get_footer_lines(width)
        footer_height = len(footer_lines)
        separator_row = max(height - footer_height - 1, 2)

        content_top = 2
        content_bottom = max(separator_row, content_top)
        content_height = max(content_bottom - content_top, 1)

        if self._show_home_dashboard(width, content_top, content_height, stdscr):
            pass
        else:
            start = 0
            if self.state.selected_index >= content_height:
                start = self.state.selected_index - content_height + 1
            rows = self.state.list_items[start : start + content_height]

            for i, item in enumerate(rows):
                row = content_top + i
                index = start + i
                prefix = "> " if index == self.state.selected_index else "  "
                text = f"{prefix}{item.title}"
                if item.subtitle:
                    text += f" ({item.subtitle})"

                attr = (
                    curses.A_REVERSE
                    if index == self.state.selected_index
                    else curses.A_NORMAL
                )
                self._safe_addnstr(stdscr, row, 0, text, width - 1, attr)

        stdscr.hline(separator_row, 0, ord("-"), width)
        for index, line in enumerate(footer_lines, start=1):
            row = separator_row + index
            if row >= height:
                break
            self._safe_addnstr(stdscr, row, 0, line, width - 1)

        stdscr.refresh()

    def _get_footer_lines(self, width: int) -> list[str]:
        usable_width = max(width - 1, 20)

        if self.state.entering_command:
            command_line = f":{self.state.command}"
            if len(command_line) <= usable_width:
                return [command_line]
            return [command_line[-usable_width:]]

        wrapped = textwrap.wrap(
            HELP_TEXT,
            width=usable_width,
            break_long_words=False,
            break_on_hyphens=False,
        )
        return wrapped or [HELP_TEXT[:usable_width]]

    def _format_duration(self, total_seconds: float | None) -> str:
        if total_seconds is None:
            return "--:--"
        total = max(0, int(total_seconds))
        minutes, seconds = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _get_home_dashboard_lines(self, width: int) -> list[str]:
        track = self.state.current_track
        subtitle = track.subtitle if track and track.subtitle else ""
        elapsed = self._format_duration(self.player.get_time_position())
        queue_size = len(self.state.queue)
        view_name = self.state.current_view

        lines = [
            "Home",
            "",
            f"Now Playing: {track.title if track else 'Nothing'}",
            f"Details: {subtitle or 'No artist or album info yet'}",
            f"Elapsed: {elapsed}",
            f"Queue: {queue_size} track(s)",
            f"View: {view_name}",
            "",
            "Front Page Shortcuts",
            "  Space or p: play/pause",
            "  n: play next track",
            "  s: search",
            "  u: my playlists",
            "  q: quit",
            "",
            "Quick Start",
            "  :search album dark side of the moon",
            "  :search artist pink floyd",
            "  :queue",
            "",
            "Other Controls",
            "  Enter: open collection / play track",
            "  Backspace or h: back",
            "  g: go to home",
            "  j/k or arrows: move",
            "  p: play first + queue selected album/playlist (in list view)",
            "  n/a: queue selected next/end (in list view)",
            "  l: play next queued track",
        ]

        wrapped_lines: list[str] = []
        usable_width = max(width - 1, 20)
        for line in lines:
            if not line:
                wrapped_lines.append("")
                continue
            wrapped_lines.extend(
                textwrap.wrap(
                    line,
                    width=usable_width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                or [line[:usable_width]]
            )
        return wrapped_lines

    def _show_home_dashboard(
        self,
        width: int,
        content_top: int,
        content_height: int,
        stdscr: curses.window,
    ) -> bool:
        if self.state.current_view != "home" or self.state.list_items:
            return False

        lines = self._get_home_dashboard_lines(width)
        for offset, line in enumerate(lines[:content_height]):
            self._safe_addnstr(stdscr, content_top + offset, 0, line, width - 1)
        return True

    def _clamp_selection(self) -> None:
        if not self.state.list_items:
            self.state.selected_index = 0
            return
        self.state.selected_index = max(
            0, min(self.state.selected_index, len(self.state.list_items) - 1)
        )

    def _start_playback(self, track: SearchResult) -> None:
        stream_url = self.backend.get_track_stream_url(track)
        self.player.play(stream_url)
        self.state.current_track = track
        self.state.status = f"Playing {track.title}"

    def _play_next_from_queue(self) -> None:
        if self.state.queue:
            next_track = self.state.queue.popleft()
            self._start_playback(next_track)
            return
        self.state.current_track = None
        self.state.status = "Queue ended"

    def _play_tracks_now(self, tracks: list[SearchResult]) -> None:
        if not tracks:
            self.state.status = "Nothing to play"
            return

        head, *rest = tracks
        self._start_playback(head)
        if rest:
            self.state.queue = deque(rest + list(self.state.queue))
            self.state.status = f"Playing {head.title} | queued {len(rest)} more"

    def _enqueue(
        self, tracks: list[SearchResult], play_immediately: bool = False
    ) -> None:
        if not tracks:
            self.state.status = "Nothing to queue"
            return

        if play_immediately:
            self._play_tracks_now(tracks)
        else:
            self.state.queue.extend(tracks)
            self.state.status = f"Queue size: {len(self.state.queue)}"

    def _show_queue(self) -> None:
        self.state.list_items = list(self.state.queue)
        self.state.selected_index = 0
        self.state.current_view = "queue"
        self.state.status = f"Queue items: {len(self.state.list_items)}"

    def _push_view_state(self) -> None:
        self.view_stack.append(
            (
                self.state.current_view,
                list(self.state.list_items),
                self.state.selected_index,
                self.state.status,
            )
        )

    def _go_back(self) -> None:
        if not self.view_stack:
            self.state.status = "No previous view"
            return

        current_view, list_items, selected_index, status = self.view_stack.pop()
        self.state.current_view = current_view
        self.state.list_items = list_items
        self.state.selected_index = selected_index
        self.state.status = status

    def _open_collection(self, selected: SearchResult) -> None:
        tracks = self.backend.list_tracks_from_result(selected)
        if not tracks:
            self.state.status = "Selected item has no playable tracks"
            return

        self._push_view_state()
        self.state.list_items = tracks
        self.state.selected_index = 0
        self.state.current_view = f"detail:{selected.kind}:{selected.title}"
        self.state.status = f"Opened {selected.title} ({len(tracks)} tracks)"

    def _show_playlists(self) -> None:
        playlists = self.backend.get_user_playlists()
        self.state.list_items = playlists
        self.state.selected_index = 0
        self.state.current_view = "playlists"
        self.state.status = f"Loaded {len(playlists)} playlists"

    def _run_search(self, args: list[str]) -> None:
        if not args:
            self.state.status = "Usage: search <query> or search <type> <query>"
            return

        kind = "tracks"
        query_parts = args
        kind_aliases = {
            "track": "tracks",
            "tracks": "tracks",
            "artist": "artists",
            "artists": "artists",
            "album": "albums",
            "albums": "albums",
            "playlist": "playlists",
            "playlists": "playlists",
        }

        if args[0] in kind_aliases and len(args) >= 2:
            kind = kind_aliases[args[0]]
            query_parts = args[1:]

        query = " ".join(query_parts).strip()
        if not query:
            self.state.status = "Search query cannot be empty"
            return

        results = self.backend.search(query=query, kind=kind)
        self.state.list_items = results
        self.state.selected_index = 0
        self.state.current_view = f"search:{kind}"
        self.state.status = f"Found {len(results)} {kind}"

    def execute_command(self, command: str) -> None:
        parts = command.strip().split()
        if not parts:
            return

        cmd, args = parts[0].lower(), parts[1:]

        if cmd == "search":
            self._run_search(args)
        elif cmd == "playlists":
            self._show_playlists()
        elif cmd == "queue":
            self._show_queue()
        elif cmd == "pause":
            self.player.pause()
            self.state.status = "Paused"
        elif cmd == "resume":
            self.player.resume()
            self.state.status = "Playing"
        elif cmd == "next":
            self._play_next_from_queue()
        elif cmd == "skip":
            try:
                amount = int(args[0]) if args else 1
            except ValueError:
                self.state.status = "Usage: skip <number>"
                return
            for _ in range(max(amount - 1, 0)):
                if self.state.queue:
                    self.state.queue.popleft()
            self._play_next_from_queue()
        elif cmd == "shuffle":
            import random

            items = list(self.state.queue)
            random.shuffle(items)
            self.state.queue = deque(items)
            self.state.status = "Queue shuffled"
        elif cmd == "home":
            self.state.current_view = "home"
            self.state.list_items = []
            self.state.selected_index = 0
            self.state.status = "Home"
        elif cmd == "quit":
            self.running = False
        else:
            self.state.status = f"Unknown command: {cmd}"

    def handle_selection(self) -> None:
        if not self.state.list_items:
            return

        selected = self.state.list_items[self.state.selected_index]
        if selected.kind == "tracks":
            self._enqueue([selected], play_immediately=True)
            return

        self._open_collection(selected)

    def _get_input_char(self, stdscr: curses.window) -> int | str | None:
        """Get a single input character, handling UTF-8 properly.
        Returns:
        - int: curses special key code (negative numbers like curses.KEY_UP)
        - str: regular character including UTF-8
        - None: no input available
        """
        try:
            ch = stdscr.get_wch()
            return ch
        except curses.error:
            return None

    def loop(self, stdscr: curses.window) -> None:
        locale.setlocale(locale.LC_ALL, "")
        curses.curs_set(0)
        stdscr.keypad(True)
        self._configure_screen(stdscr)
        stdscr.nodelay(True)
        stdscr.timeout(150)

        self.ensure_logged_in()

        self.state.status = "Ready"
        self.state.list_items = []

        while self.running:
            if self.player.finished():
                self._play_next_from_queue()

            self._apply_backend_notice_to_status()

            self._clamp_selection()
            self.draw(stdscr)
            ch = self._get_input_char(stdscr)

            if ch is None:
                continue

            ch_ord = ord(ch) if isinstance(ch, str) and len(ch) == 1 else ch

            if self.state.entering_command:
                if ch_ord in (10, 13):
                    command = self.state.command
                    self.state.command = ""
                    self.state.entering_command = False
                    try:
                        self.execute_command(command)
                    except Exception as exc:  # noqa: BLE001
                        self.state.status = f"Command failed: {exc}"
                elif ch_ord == 27:
                    self.state.entering_command = False
                    self.state.command = ""
                elif ch_ord in (curses.KEY_BACKSPACE, 127, 8):
                    self.state.command = self.state.command[:-1]
                elif isinstance(ch, str) and ch.isprintable():
                    self.state.command += ch
                continue

            if ch_ord == ord("q"):
                self.running = False
            elif ch_ord == ord("g"):
                self.execute_command("home")
            elif ch_ord == ord(":"):
                self.state.entering_command = True
            elif ch_ord == ord("j") or ch == curses.KEY_DOWN:
                self.state.selected_index += 1
            elif ch_ord == ord("k") or ch == curses.KEY_UP:
                self.state.selected_index -= 1
            elif ch_ord in (curses.KEY_BACKSPACE, 127, 8, ord("h")):
                self._go_back()
            elif ch_ord in (10, 13):
                try:
                    self.handle_selection()
                except Exception as exc:  # noqa: BLE001
                    self.state.status = f"Selection failed: {exc}"
            elif ch_ord == ord("l"):
                self._play_next_from_queue()
            elif ch_ord == ord("a"):
                if self.state.list_items:
                    selected = self.state.list_items[self.state.selected_index]
                    tracks = self.backend.list_tracks_from_result(selected)
                    self._enqueue(tracks, play_immediately=False)
            elif ch_ord == ord("p") and self.state.current_view != "home":
                if not self.state.list_items:
                    self.state.status = "Nothing selected"
                else:
                    selected = self.state.list_items[self.state.selected_index]
                    if selected.kind in ("albums", "playlists"):
                        tracks = self.backend.list_tracks_from_result(selected)
                        self._enqueue(tracks, play_immediately=True)
                    else:
                        self.state.status = (
                            "p shortcut plays+queues selected album/playlist"
                        )
            elif (
                ch_ord == ord(" ") or ch_ord == ord("p")
            ) and self.state.current_view == "home":
                if self.state.current_track:
                    if self.player.is_paused:
                        self.player.resume()
                        self.state.status = "Playing"
                    else:
                        self.player.pause()
                        self.state.status = "Paused"
                else:
                    self.state.status = "No track currently playing"
            elif ch_ord == ord("s") and self.state.current_view == "home":
                self.state.entering_command = True
                self.state.command = "search "
            elif ch_ord == ord("u") and self.state.current_view == "home":
                try:
                    self._show_playlists()
                except Exception as exc:  # noqa: BLE001
                    self.state.status = f"Failed to load playlists: {exc}"
            elif ch_ord == ord("n"):
                if self.state.current_view == "home":
                    self._play_next_from_queue()
                elif self.state.list_items:
                    selected = self.state.list_items[self.state.selected_index]
                    tracks = self.backend.list_tracks_from_result(selected)
                    if tracks:
                        for track in reversed(tracks):
                            self.state.queue.appendleft(track)
                        self.state.status = f"Added {len(tracks)} as next"

        self.player.stop()


def run() -> None:
    if shutil.which("mpv") is None:
        raise SystemExit("mpv not found. Install mpv first.")

    app = CursesTidalApp()
    try:
        curses.wrapper(app.loop)
    except KeyboardInterrupt:
        pass
    except Exception:  # noqa: BLE001
        print("Fatal error in curses app:\n")
        print(traceback.format_exc())
