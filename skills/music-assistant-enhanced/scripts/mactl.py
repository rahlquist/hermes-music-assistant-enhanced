#!/usr/bin/env python3
import glob, os, sys
# Ensure music-assistant-client is importable even when the default python3
# doesn't have it on its path (it's installed under a Hermes tool python).
for _p in glob.glob("/home/rahlquist/.hermes/tools/python-3.14.*/lib/python*/site-packages"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
"""
Music Assistant Control CLI
Control playback, search library, manage queues.
"""

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Config - MUST be set via environment variables
MA_URL = os.environ.get("MA_URL", "")
MA_TOKEN = os.environ.get("MA_TOKEN", "")
MA_PLAYER = os.environ.get("MA_PLAYER", "")


def api_search(query: str, media_types=None, limit: int = 10):
    """Search library using the official Music Assistant client (WebSocket).

    The REST ``music/search`` endpoint returns 500 on some MA versions even
    though search works in the web UI and via the official client. This uses
    the official client library which speaks the WebSocket protocol.
    """
    try:
        import asyncio
        import aiohttp
        from music_assistant_client import MusicAssistantClient
    except ImportError:
        print("Error: music-assistant-client is required for search.", file=sys.stderr)
        print("Install with: pip install music-assistant-client", file=sys.stderr)
        sys.exit(1)

    async def _search():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            res = await client.music.search(query, media_types=media_types or ["track", "album", "artist", "playlist"], limit=limit)
            await client.disconnect()
            return res

    try:
        res = asyncio.run(_search())
    except Exception as e:
        print(f"Search error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    # Flatten SearchResults into a list of items with media_type
    items = []
    for attr, mtype in [("artists", "artist"), ("albums", "album"), ("tracks", "track"),
                        ("playlists", "playlist"), ("radio", "radio"),
                        ("audiobooks", "audiobook"), ("podcasts", "podcast")]:
        for it in getattr(res, attr, []) or []:
            items.append({"name": getattr(it, "name", "Unknown"),
                          "media_type": mtype,
                          "uri": getattr(it, "uri", "")})
    return items[:limit] if limit else items


def api_play_media(queue_id: str, uri: str):
    """Play media by URI using the official client (WebSocket).

    REST ``player_queues/play_media`` returns 500 on some MA versions.
    """
    try:
        import asyncio
        import aiohttp
        from music_assistant_client import MusicAssistantClient
    except ImportError:
        print("Error: music-assistant-client is required.", file=sys.stderr)
        print("Install with: pip install music-assistant-client", file=sys.stderr)
        sys.exit(1)

    async def _play():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            await client.player_queues.play_media(queue_id, uri)
            await client.disconnect()

    try:
        asyncio.run(_play())
    except Exception as e:
        print(f"Play error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


def api(cmd: str, args: dict = None) -> any:
    """Send JSON-RPC command to Music Assistant API."""
    if not MA_URL or not MA_TOKEN:
        print("Error: MA_URL and MA_TOKEN must be set as environment variables.", file=sys.stderr)
        print("\nSetup:", file=sys.stderr)
        print('  export MA_URL="http://your-server:8095/api"', file=sys.stderr)
        print('  export MA_TOKEN="your_bearer_token"', file=sys.stderr)
        print('  export MA_PLAYER="your_player_id"  # optional', file=sys.stderr)
        print("\nYou can find your token in Music Assistant settings.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "message_id": "1",
        "command": cmd,
    }
    if args:
        payload["args"] = args

    req = Request(
        MA_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MA_TOKEN}",
        },
    )

    try:
        with urlopen(req, timeout=10) as resp:
            data = resp.read().decode()
            if not data:
                return None
            return json.loads(data)
    except HTTPError as e:
        body = e.read().decode()
        # Music Assistant's music/search is known to return 500 on some
        # versions even though search works in the web UI. Surface a
        # helpful message instead of a bare error code.
        if e.code == 500 and cmd == "music/search":
            print("Search failed (MA server returned 500). This is a known "
                  "Music Assistant issue on some versions.", file=sys.stderr)
            print("Workarounds:", file=sys.stderr)
            print("  - Search in the MA web UI and use: play-uri <uri>", file=sys.stderr)
            print("  - Or pick from recently played: recent", file=sys.stderr)
            print(f"  (server said: {body})", file=sys.stderr)
        else:
            print(f"API Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        print(f"  Make sure MA_URL is correct: {MA_URL}", file=sys.stderr)
        sys.exit(1)


def get_player():
    """Get player ID - from env or auto-detect first available."""
    global MA_PLAYER
    if MA_PLAYER:
        return MA_PLAYER
    
    players = api("players/all")
    if players and len(players) > 0:
        MA_PLAYER = players[0].get("player_id", "")
        return MA_PLAYER
    
    print("No players found. Make sure Music Assistant has at least one player configured.", file=sys.stderr)
    sys.exit(1)


def cmd_play(args):
    """Play/pause toggle."""
    player = get_player()
    api("player_queues/play_pause", {"queue_id": player})
    print("▶️ Toggled play/pause")


def cmd_pause(args):
    """Pause playback."""
    player = get_player()
    api("player_queues/play_pause", {"queue_id": player})
    print("⏸️ Paused")


def cmd_stop(args):
    """Stop playback."""
    player = get_player()
    api("player_queues/stop", {"queue_id": player})
    print("⏹️ Stopped")


def cmd_next(args):
    """Next track."""
    player = get_player()
    api("player_queues/next", {"queue_id": player})
    print("⏭️ Next track")


def cmd_prev(args):
    """Previous track."""
    player = get_player()
    api("player_queues/previous", {"queue_id": player})
    print("⏮️ Previous track")


def cmd_volume(args):
    """Set volume (0-100)."""
    player = get_player()
    api("players/cmd", {
        "player_id": player,
        "cmd": "volume_set",
        "volume_level": args.level,
    })
    print(f"🔊 Volume set to {args.level}%")


def cmd_mute(args):
    """Mute."""
    player = get_player()
    api("players/cmd", {
        "player_id": player,
        "cmd": "volume_mute",
        "volume_muted": True,
    })
    print("🔇 Muted")


def cmd_unmute(args):
    """Unmute."""
    player = get_player()
    api("players/cmd", {
        "player_id": player,
        "cmd": "volume_mute",
        "volume_muted": False,
    })
    print("🔊 Unmuted")


def cmd_shuffle(args):
    """Toggle shuffle."""
    player = get_player()
    state = args.state if args.state else "true"
    api("player_queues/shuffle", {
        "queue_id": player,
        "shuffle_enabled": state.lower() == "true",
    })
    print(f"🔀 Shuffle {'enabled' if state.lower() == 'true' else 'disabled'}")


def cmd_repeat(args):
    """Set repeat mode."""
    player = get_player()
    mode = args.mode if args.mode else "all"
    api("player_queues/repeat", {
        "queue_id": player,
        "repeat_mode": mode,
    })
    modes = {"off": "➡️", "all": "🔁", "one": "🔂"}
    print(f"{modes.get(mode, '🔁')} Repeat mode: {mode}")


def cmd_clear(args):
    """Clear queue."""
    player = get_player()
    api("player_queues/clear", {"queue_id": player})
    print("🗑️ Queue cleared")


def cmd_status(args):
    """Show player status."""
    players = api("players/all")
    if not players:
        print("No players found")
        return

    for p in players:
        state_icon = {"playing": "▶️", "paused": "⏸️", "idle": "⏹️"}.get(p.get("state", "idle"), "❓")
        print(f"\n{state_icon} **{p.get('display_name', p.get('name', 'Unknown'))}**")
        print(f"   State: {p.get('state', 'idle')}")
        print(f"   Volume: {p.get('volume_level', 0)}%")
        if p.get("volume_muted"):
            print("   🔇 Muted")

        media = p.get("current_media")
        if media:
            print(f"\n   🎵 Now Playing:")
            print(f"      {media.get('title', 'Unknown')}")
            if media.get("artist"):
                print(f"      by {media.get('artist')}")
            if media.get("album"):
                print(f"      from {media.get('album')}")


def cmd_queue(args):
    """Show queue status."""
    queues = api("player_queues/all")
    if not queues:
        print("No queues found")
        return

    for q in queues:
        state_icon = {"playing": "▶️", "paused": "⏸️", "idle": "⏹️"}.get(q.get("state", "idle"), "❓")
        print(f"\n{state_icon} **{q.get('display_name', 'Queue')}**")
        print(f"   Items: {q.get('items', 0)}")
        print(f"   State: {q.get('state', 'idle')}")
        print(f"   Shuffle: {'on' if q.get('shuffle_enabled') else 'off'}")
        print(f"   Repeat: {q.get('repeat_mode', 'off')}")

        current = q.get("current_item")
        if current:
            print(f"\n   🎵 Current: {current.get('name', 'Unknown')}")

        next_item = q.get("next_item")
        if next_item:
            print(f"   ⏭️ Next: {next_item.get('name', 'Unknown')}")


def cmd_queue_items(args):
    """List queue items."""
    player = get_player()
    limit = args.limit if args.limit else 20
    result = api("player_queues/items", {
        "queue_id": player,
        "limit": limit,
        "offset": 0,
    })

    if not result:
        print("Queue is empty")
        return

    items = result if isinstance(result, list) else result.get("items", [])
    print(f"\n📜 Queue ({len(items)} items):\n")
    for i, item in enumerate(items[:limit], 1):
        name = item.get("name", "Unknown")
        duration = item.get("duration", 0)
        dur_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else ""
        print(f"   {i:3}. {name} {' ' + dur_str if dur_str else ''}")


def cmd_search(args):
    """Search library."""
    query = " ".join(args.query)
    media_types = args.type if args.type else ["track", "album", "artist", "playlist"]

    result = api_search(query, media_types=media_types, limit=args.limit if args.limit else 10)

    if not result:
        print(f"No results for '{query}'")
        return

    print(f"\n🔍 Results for '{query}':\n")

    type_icons = {"track": "🎵", "album": "💿", "artist": "👤", "playlist": "📋"}

    for item in result:
        icon = type_icons.get(item.get("media_type", "track"), "🎵")
        name = item.get("name", "Unknown")
        item_type = item.get("media_type", "track")
        uri = item.get("uri", "")

        # Artist info for tracks/albums
        artist = ""
        if item.get("artists"):
            artist = f" by {item['artists'][0].get('name', '')}"

        print(f"   {icon} **{name}**{artist} ({item_type})")
        print(f"      URI: {uri}\n")


def cmd_play_search(args):
    """Search and play the first result."""
    player = get_player()
    query = " ".join(args.query)

    result = api_search(query, media_types=["track", "album", "playlist"], limit=1)

    if not result or len(result) == 0:
        print(f"No results for '{query}'")
        return

    item = result[0]
    uri = item.get("uri", "")
    name = item.get("name", "Unknown")
    item_type = item.get("media_type", "track")

    print(f"🎵 Playing: {name} ({item_type})")

    api_play_media(player, uri)


def cmd_play_uri(args):
    """Play by URI."""
    player = get_player()
    uri = args.uri
    api_play_media(player, uri)
    print(f"🎵 Playing: {uri}")


def cmd_recent(args):
    """Show recently played."""
    limit = args.limit if args.limit else 10
    result = api("music/recently_played_items", {"limit": limit})

    if not result:
        print("No recent items")
        return

    print(f"\n🕐 Recently played:\n")

    type_icons = {"track": "🎵", "album": "💿", "artist": "👤", "playlist": "📋"}

    for item in result[:limit]:
        icon = type_icons.get(item.get("media_type", "track"), "🎵")
        name = item.get("name", "Unknown")
        item_type = item.get("media_type", "track")
        print(f"   {icon} {name} ({item_type})")


def cmd_sync(args):
    """Trigger library sync."""
    api("music/sync", {})
    print("🔄 Library sync started")


def cmd_players(args):
    """List all players."""
    players = api("players/all")
    if not players:
        print("No players found")
        return

    print("\n🎚️ Available Players:\n")
    for p in players:
        state_icon = {"playing": "▶️", "paused": "⏸️", "idle": "⏹️"}.get(p.get("state", "idle"), "❓")
        print(f"   {state_icon} {p.get('display_name', p.get('name', 'Unknown'))}")
        print(f"      ID: {p.get('player_id', 'unknown')}")
        print(f"      State: {p.get('state', 'idle')}")
        print()


def api_enqueue(uri: str, option: str = "add"):
    """Enqueue media by URI using official client."""
    import asyncio, aiohttp
    from music_assistant_client import MusicAssistantClient
    from music_assistant_models.enums import QueueOption
    async def _run():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            player = MA_PLAYER or (await client.players.get_all())[0].player_id if False else None
            # resolve player
            await client.disconnect()
    # simpler: use REST player_queues/play_media with option
    api("player_queues/play_media", {"queue_id": get_player(), "media": uri, "option": option})
    print(f"➕ Enqueued: {uri}")


def cmd_enqueue(args):
    uri = args.uri
    api_enqueue(uri, "add")


def cmd_remove_item(args):
    idx = args.index
    player = get_player()
    import asyncio, aiohttp
    from music_assistant_client import MusicAssistantClient
    async def _run():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            await client.player_queues.delete_item(player, idx)
            await client.disconnect()
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    print(f"🗑️ Removed queue item {idx}")


def cmd_move_item(args):
    player = get_player()
    import asyncio, aiohttp
    from music_assistant_client import MusicAssistantClient
    async def _run():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            await client.player_queues.move_item(player, args.item, args.shift)
            await client.disconnect()
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    print(f"↕️ Moved item {args.item} by {args.shift}")


def cmd_play_index(args):
    player = get_player()
    import asyncio, aiohttp
    from music_assistant_client import MusicAssistantClient
    async def _run():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            await client.player_queues.play_index(player, args.index)
            await client.disconnect()
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    print(f"▶️ Playing queue index {args.index}")


def cmd_favorite(args):
    uri = args.uri
    import asyncio, aiohttp
    from music_assistant_client import MusicAssistantClient
    async def _run():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            await client.music.add_item_to_favorites(uri)
            await client.disconnect()
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    print(f"⭐ Added to favorites: {uri}")


def cmd_unfavorite(args):
    media_type = args.type
    item_id = args.id
    import asyncio, aiohttp
    from music_assistant_client import MusicAssistantClient
    async def _run():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            await client.music.remove_item_from_favorites(media_type, item_id)
            await client.disconnect()
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    print(f"💔 Removed from favorites: {item_id}")


def cmd_group(args):
    player = get_player()
    target = args.target
    import asyncio, aiohttp
    from music_assistant_client import MusicAssistantClient
    async def _run():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            await client.players.group(player, target)
            await client.disconnect()
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    print(f"🔗 Grouped {player} → {target}")


def cmd_ungroup(args):
    player = get_player()
    import asyncio, aiohttp
    from music_assistant_client import MusicAssistantClient
    async def _run():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            await client.players.ungroup(player)
            await client.disconnect()
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    print(f"✂️ Ungrouped {player}")


def cmd_transfer(args):
    source = get_player()
    target = args.target
    import asyncio, aiohttp
    from music_assistant_client import MusicAssistantClient
    async def _run():
        async with aiohttp.ClientSession() as sess:
            client = MusicAssistantClient(MA_URL.replace("/api", ""), sess, token=MA_TOKEN)
            await client.connect()
            await client.player_queues.transfer(source, target)
            await client.disconnect()
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    print(f"➡️ Transferred {source} → {target}")
def main():
    parser = argparse.ArgumentParser(
        description="Music Assistant Control CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Playback
    subparsers.add_parser("play", help="Play/pause toggle")
    subparsers.add_parser("pause", help="Pause playback")
    subparsers.add_parser("stop", help="Stop playback")
    subparsers.add_parser("next", help="Next track")
    subparsers.add_parser("prev", help="Previous track")

    # Volume
    vol_parser = subparsers.add_parser("volume", help="Set volume (0-100)")
    vol_parser.add_argument("level", type=int, help="Volume level 0-100")
    subparsers.add_parser("mute", help="Mute")
    subparsers.add_parser("unmute", help="Unmute")

    # Queue
    shuffle_parser = subparsers.add_parser("shuffle", help="Toggle shuffle")
    shuffle_parser.add_argument("state", nargs="?", choices=["true", "false"], help="on/off")
    repeat_parser = subparsers.add_parser("repeat", help="Set repeat mode")
    repeat_parser.add_argument("mode", nargs="?", choices=["off", "all", "one"], help="Repeat mode")
    subparsers.add_parser("clear", help="Clear queue")

    # Status
    subparsers.add_parser("status", help="Show player status")
    subparsers.add_parser("queue", help="Show queue status")
    qi_parser = subparsers.add_parser("queue-items", help="List queue items")
    qi_parser.add_argument("--limit", type=int, default=20, help="Max items to show")
    subparsers.add_parser("players", help="List all players")

    # Search & Play
    search_parser = subparsers.add_parser("search", help="Search library")
    search_parser.add_argument("query", nargs="+", help="Search query")
    search_parser.add_argument("--type", "-t", nargs="+", default=["track", "album", "artist", "playlist"],
                               choices=["track", "album", "artist", "playlist"], help="Media types")
    search_parser.add_argument("--limit", "-l", type=int, default=10, help="Max results")

    play_parser = subparsers.add_parser("play-search", aliases=["ps"], help="Search and play first result")
    play_parser.add_argument("query", nargs="+", help="Search query")

    uri_parser = subparsers.add_parser("play-uri", help="Play by URI")
    uri_parser.add_argument("uri", help="Media URI (e.g. spotify://track/xxx)")

    # Library
    recent_parser = subparsers.add_parser("recent", help="Show recently played")
    recent_parser.add_argument("--limit", "-l", type=int, default=10, help="Max items")
    subparsers.add_parser("sync", help="Trigger library sync")

    # Queue extras
    enq_parser = subparsers.add_parser("enqueue", help="Enqueue media by URI (add to queue)")
    enq_parser.add_argument("uri", help="Media URI")
    ri_parser = subparsers.add_parser("remove-item", help="Remove queue item by index/id")
    ri_parser.add_argument("index", help="Queue item index or id")
    mi_parser = subparsers.add_parser("move-item", help="Move queue item")
    mi_parser.add_argument("item", help="Queue item id")
    mi_parser.add_argument("shift", type=int, help="Position shift (e.g. -1, 1)")
    pi_parser = subparsers.add_parser("play-index", help="Play queue item at index")
    pi_parser.add_argument("index", help="Queue index")
    fav_parser = subparsers.add_parser("favorite", help="Add URI to favorites")
    fav_parser.add_argument("uri", help="Media URI")
    unfav_parser = subparsers.add_parser("unfavorite", help="Remove from favorites")
    unfav_parser.add_argument("type", help="Media type (track/album/...)")
    unfav_parser.add_argument("id", help="Library item id")
    grp_parser = subparsers.add_parser("group", help="Group player into target player")
    grp_parser.add_argument("target", help="Target player id")
    subparsers.add_parser("ungroup", help="Ungroup player")
    tr_parser = subparsers.add_parser("transfer", help="Transfer playback to target player")
    tr_parser.add_argument("target", help="Target player id")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Map commands to functions
    commands = {
        "play": cmd_play,
        "pause": cmd_pause,
        "stop": cmd_stop,
        "next": cmd_next,
        "prev": cmd_prev,
        "volume": cmd_volume,
        "mute": cmd_mute,
        "unmute": cmd_unmute,
        "shuffle": cmd_shuffle,
        "repeat": cmd_repeat,
        "clear": cmd_clear,
        "status": cmd_status,
        "queue": cmd_queue,
        "queue-items": cmd_queue_items,
        "players": cmd_players,
        "search": cmd_search,
        "play-search": cmd_play_search,
        "ps": cmd_play_search,
        "play-uri": cmd_play_uri,
        "recent": cmd_recent,
        "sync": cmd_sync,
        "enqueue": cmd_enqueue,
        "remove-item": cmd_remove_item,
        "move-item": cmd_move_item,
        "play-index": cmd_play_index,
        "favorite": cmd_favorite,
        "unfavorite": cmd_unfavorite,
        "group": cmd_group,
        "ungroup": cmd_ungroup,
        "transfer": cmd_transfer,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()