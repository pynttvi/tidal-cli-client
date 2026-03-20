# tidal-cli-client

`tidal-cli-client` is now a Python curses client for TIDAL focused on keyboard-first playback, queue control, and terminal-friendly search.

This workspace started from the original Node.js `okonek/tidal-cli-client` project, but the legacy JavaScript implementation has been removed here. What remains is the Python port and its supporting files.

This is an unofficial community project and is not affiliated with, endorsed by, or sponsored by TIDAL.

## Legal

You are responsible for complying with TIDAL terms of service, applicable copyright rules, and local laws when using this software.

## Features

- Terminal UI built with curses
- Search for tracks, albums, artists, and playlists
- Open albums, artists, and playlists as detail views
- Queue management with next, append, skip, and shuffle
- `mpv` playback backend
- Persisted OAuth session with automatic refresh
- UTF-8 command input for searches
- Home dashboard with current track, elapsed time, and shortcuts

## Requirements

- Linux
- Python 3.10+
- `mpv` available in `PATH`

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Install From AUR

Using an AUR helper:

```bash
yay -S tidal-cli-client-python
```

or

```bash
paru -S tidal-cli-client-python
```

Manual AUR install:

```bash
git clone https://aur.archlinux.org/tidal-cli-client-python.git
cd tidal-cli-client-python
makepkg -fs
sudo pacman -U tidal-cli-client-python-*.pkg.tar.*
```

## Run

```bash
python3 python_tidal_cli.py
```

## Install As `tidal-cli` Command

### Generic system install (`/usr/bin/tidal-cli`)

Use the included installer:

```bash
sudo ./scripts/install-system.sh
```

This installs app files to `/usr/lib/tidal-cli-client`, creates an isolated runtime venv there, and installs a launcher at `/usr/bin/tidal-cli`.

Run:

```bash
tidal-cli
```


## Screenshot

```text
tidal-cli-client (Python curses port) | Status: Ready | Playing: Time
---------------------------------------------------------------------
Home

Now Playing: Time
Details: Pink Floyd - The Dark Side of the Moon
Elapsed: 02:03
Queue: 2 track(s)
View: home

Front Page Shortcuts
  Space or p: play/pause
  n: play next track
  s: search
  q: quit

---------------------------------------------------------------------
Commands: search <query> | search <type> <query> | playlists | queue
```

## First Run

The app reads configuration from:

- `~/.config/tidal-cli-client/app.json`

OAuth sessions are stored at:

- `~/.config/tidal-cli-client/oauth-session.json`

On first launch, the app uses `tidalapi` OAuth login and persists the session for future launches.

## Manual

### Navigation

- `:` open the command line
- `j` / `k` or arrow keys move selection
- `Enter` open a collection or play a track
- `Backspace` or `h` go back to the previous view
- `g` return to the home page
- `q` quit

### Home Shortcuts

- `Space` or `p` toggle play/pause
- `n` play the next queued track
- `s` open `search ` directly from the home page

### Queue Shortcuts

- `a` add the selected item to the end of the queue
- `n` add the selected item as next when browsing a list
- `l` immediately start the next queued track

### Commands

| Command | What it does | Example |
| --- | --- | --- |
| `search <query>` | Search tracks by default | `search kylmästä lämpimään` |
| `search <type> <query>` | Search a specific type | `search album dark side of the moon` |
| `playlists` | Load your playlists | `playlists` |
| `queue` | Show queued tracks | `queue` |
| `pause` | Pause playback | `pause` |
| `resume` | Resume playback | `resume` |
| `next` | Play next queued track | `next` |
| `skip <n>` | Skip `n` queued tracks | `skip 3` |
| `shuffle` | Shuffle the queue | `shuffle` |
| `home` | Return to the home screen | `home` |
| `quit` | Exit the app | `quit` |

### Search Tips

- Singular and plural search kinds both work: `track` / `tracks`, `album` / `albums`, `artist` / `artists`, `playlist` / `playlists`
- UTF-8 input is supported in the command bar
- Selecting an album, artist, or playlist opens its tracks instead of auto-playing everything

## Playback Notes

- Playback is handled by `mpv`
- The current track and elapsed playback time appear on the home dashboard
- When the current track ends, the next queued track starts automatically

## Project Layout

- `py_tidal_cli/` main application package
- `python_tidal_cli.py` entry point
- `requirements.txt` Python dependencies

### AUR packaging config

AUR packaging files are provided in `packaging/aur/PKGBUILD`.

If your repository/tag is not published yet, use the local packaging file instead:

```bash
cd packaging/aur
makepkg -p PKGBUILD.local -fs
```

This builds from your local working tree and does not download from GitHub.

The package is configured to build from the GitHub tag archive at:

- `https://github.com/pynttvi/tidal-cli-client/archive/refs/tags/v${pkgver}.tar.gz`

Before publishing to AUR, update `pkgver`, compute the real checksum, and regenerate `.SRCINFO`.

You can do that in one step:

```bash
./scripts/update-aur-metadata.sh 0.1.1
```

Or without changing version:

```bash
./scripts/update-aur-metadata.sh
```

Quick local package build (from repo root):

```bash
cd packaging/aur
updpkgsums
makepkg --printsrcinfo > .SRCINFO
makepkg -fs
```

Install built package:

```bash
sudo pacman -U ./tidal-cli-client-python-*.pkg.tar.*
```

### One-command release (GitHub + AUR)

To publish a version to both GitHub and AUR in one command:

```bash
./scripts/release-github-aur.sh 0.1.1
```

What it does:

- Updates `packaging/aur/PKGBUILD` and `packaging/aur/.SRCINFO` to the version
- Commits those metadata changes (if needed)
- Pushes your current branch to `origin`
- Creates and pushes Git tag `v<version>`
- Clones AUR repo `tidal-cli-client-python`, copies `PKGBUILD` + `.SRCINFO`, commits, and pushes

Requirements:

- Clean local git working tree
- `origin` remote configured and push access to GitHub
- AUR account + SSH key configured for `ssh://aur@aur.archlinux.org/tidal-cli-client-python.git`

## Legacy Context

This codebase is a cleaned continuation of the original `okonek/tidal-cli-client` idea, but it is no longer the Node.js application. If you need the historical JavaScript implementation, use the upstream Node repository rather than this cleaned Python-only workspace.
