# hermes-music-assistant-enhanced

Hermes skill: control [Music Assistant](https://github.com/music-assistant) (Home Assistant music server) — playback, volume, queue management, library search, favorites, and multi-room grouping.

## Install into Hermes

```bash
hermes skills install \
  https://raw.githubusercontent.com/rahlquist/hermes-music-assistant-enhanced/main/music-assistant-enhanced/SKILL.md \
  --yes
```

Or clone and copy `music-assistant-enhanced/` into `~/.hermes/skills/`.

## What it does

- Play/pause/stop, next/prev track
- Volume, mute/unmute
- Shuffle and repeat modes
- Queue management: clear, list items, enqueue, remove, move, play-from-index
- Library search (WebSocket-based, avoids MA 500 errors)
- Play by search query or URI
- Recently played, library sync
- Favorites: add/remove
- Multi-room: group, ungroup, transfer playback
- Status and player listing

## Setup

1. Set environment variables:
   ```bash
   export MA_URL="http://YOUR_SERVER:8095/api"   # note the /api suffix
   export MA_TOKEN="YOUR_LONG_LIVED_ACCESS_TOKEN"
   export MA_PLAYER="your_player_id"             # optional, auto-detected
   ```

2. Install the WebSocket client (required for search/play-by-URI):
   ```bash
   pip install music-assistant-client
   ```

3. Smoke test:
   ```bash
   ./scripts/mactl.py players
   ./scripts/mactl.py status
   ```

## Usage

```bash
# Basic controls
./scripts/mactl.py play          # Play/pause toggle
./scripts/mactl.py next          # Skip track
./scripts/mactl.py volume 75     # Set volume to 75%

# Search and play
./scripts/mactl.py search "nirvana"
./scripts/mactl.py play-search "pink floyd"
./scripts/mactl.py play-uri "spotify://track/4gHnSNHs8RyVukKoWdS99f"

# Queue management
./scripts/mactl.py enqueue spotify://track/xxx   # Add to queue
./scripts/mactl.py remove-item 3                 # Remove queue item
./scripts/mactl.py play-index 2                   # Play queue item at index

# Favorites
./scripts/mactl.py favorite spotify://track/xxx

# Multi-room
./scripts/mactl.py group <target_player_id>
./scripts/mactl.py transfer <target_player_id>
```

## Files

| File | Purpose |
|------|---------|
| `music-assistant-enhanced/SKILL.md` | Skill definition (Hermes loads this) |
| `music-assistant-enhanced/scripts/mactl.py` | Control CLI |

## Credits

- Base skill: [rodrigosiviero/music-assistant](https://clawhub.ai/rodrigosiviero/skills/music-assistant) on ClawHub
- Extension: rahlquist — WebSocket search/play fix, enqueue, queue item management, favorites, multi-room grouping/transfer
" path">
/home/rahlquist/.hermes/cache/scratch/music-assistant-skill/README.md