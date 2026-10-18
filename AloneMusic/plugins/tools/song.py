#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
# This file is part of < https://github.com/TheAloneTeam/AloneMusic > project.
#

import asyncio
import os
import re
import urllib.request
from pyrogram import filters
from pyrogram.types import Message

import config
from AloneMusic import Spotify, YouTube, app
from config import BANNED_USERS


def _dl_thumb(url: str, path: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(path, "wb") as f:
        f.write(resp.read())


# Helper function to download and send a single track by query or YT track details
async def process_and_send_track(
    client,
    message: Message,
    mystic: Message,
    query: str,
    is_video: bool = False,
    index: int = None,
    total: int = None,
):
    try:
        if await Spotify.valid(query) and "track" in query:
            details, track_id = await Spotify.track(query)
        else:
            details, track_id = await YouTube.track(query)
    except Exception as e:
        if mystic:
            await mystic.edit_text(f"» Failed to fetch details for `{query}`: {e}")
        return

    if not details or not track_id:
        if mystic:
            await mystic.edit_text(f"» Song not found for `{query}`.")
        return

    title = details.get("title", "Song")
    duration = details.get("duration_min", "0:00")
    thumb_url = details.get("thumb")
    ytlink = details.get("link", f"https://www.youtube.com/watch?v={track_id}")

    progress_prefix = f"[{index}/{total}] " if index and total else ""

    if mystic:
        await mystic.edit_text(
            f"📥 **{progress_prefix}Downloading:** `{title}`..."
        )

    thumb_path = f"downloads/thumb_{track_id}.jpg"
    if thumb_url:
        try:
            await asyncio.to_thread(_dl_thumb, thumb_url, thumb_path)
        except Exception:
            thumb_path = None
    else:
        thumb_path = None

    file_path = None
    try:
        formats, _ = await YouTube.formats(ytlink)
        format_id = "bestaudio/best"
        if formats:
            if is_video:
                for f in formats:
                    if f.get("format_id") and "mp4" in str(f.get("ext", "")):
                        format_id = f["format_id"]
                        break
            else:
                for f in formats:
                    if f.get("format_id") and "audio" in str(f.get("format_note", "")).lower():
                        format_id = f["format_id"]
                        break

        clean_title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]
        if not is_video:
            try:
                file_path = await Spotify.download_track(query, message.chat.id)
            except Exception:
                file_path = None

        if not file_path:
            dl_res = await YouTube.download(
                ytlink,
                mystic,
                songvideo=is_video,
                songaudio=not is_video,
                format_id=format_id,
                title=clean_title,
            )
            if isinstance(dl_res, tuple):
                file_path = dl_res[0]
            else:
                file_path = dl_res

        if not file_path or not os.path.exists(file_path):
            if mystic:
                await mystic.edit_text(f"» Failed to download `{title}`.")
            return

        if mystic:
            await mystic.edit_text(f"📤 **{progress_prefix}Sending audio:** `{title}`...")

        caption = (
            f"🎵 **ᴛɪᴛʟᴇ:** [{title}]({ytlink})\n"
            f"⏱ **ᴅᴜʀᴀᴛɪᴏɴ:** `{duration}`\n"
            f"🥀 **ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ʙʏ:** {message.from_user.mention}"
        )

        if is_video:
            await message.reply_video(
                video=file_path,
                caption=caption,
                thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
            )
        else:
            await message.reply_audio(
                audio=file_path,
                caption=caption,
                title=title,
                performer="Spotify / YouTube",
                thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
            )

        if mystic:
            await mystic.delete()

    except Exception as e:
        if mystic:
            await mystic.edit_text(f"» Error processing `{title}`: {e}")

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass


# Automatic Spotify Link Detection & Downloader
@app.on_message(
    filters.regex(r"^https?://(open|music)\.spotify\.com/(track|playlist|album|artist)/[a-zA-Z0-9]+")
    & ~BANNED_USERS
)
async def spotify_link_auto_downloader(client, message: Message, url: str = None):
    if not url:
        url = message.text.strip()
    mystic = await message.reply_text("🔎 **Processing Spotify link...**")

    if "track" in url:
        await process_and_send_track(client, message, mystic, url, is_video=False)
    elif "playlist" in url or "album" in url or "artist" in url:
        try:
            if "playlist" in url:
                tracks, _id = await Spotify.playlist(url)
                type_str = "Playlist"
            elif "album" in url:
                tracks, _id = await Spotify.album(url)
                type_str = "Album"
            else:
                tracks, _id = await Spotify.artist(url)
                type_str = "Artist Top Tracks"

            if not tracks:
                return await mystic.edit_text(f"» Could not extract tracks from this Spotify {type_str}.")

            total = len(tracks)
            await mystic.edit_text(f"🎶 **Found {total} tracks in Spotify {type_str}. Starting download...**")
            await asyncio.sleep(2)

            for idx, track_query in enumerate(tracks, start=1):
                track_status = await message.reply_text(
                    f"🔄 **Processing [{idx}/{total}]:** `{track_query}`"
                )
                await process_and_send_track(
                    client,
                    message,
                    track_status,
                    track_query,
                    is_video=False,
                    index=idx,
                    total=total,
                )
                await asyncio.sleep(1)

            await mystic.edit_text(f"✅ **Completed downloading all {total} tracks from Spotify {type_str}!**")
        except Exception as e:
            await mystic.edit_text(f"» Error processing Spotify link: {e}")


# Command based downloader (/song, /vsong, /download, /vdownload)
@app.on_message(
    filters.command(["song", "vsong", "download", "vdownload"])
    & ~BANNED_USERS
)
async def song_command_downloader(client, message: Message):
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            "» ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ a sᴏɴɢ ɴᴀᴍᴇ or ʟɪɴᴋ to ᴅᴏᴡɴʟᴏᴀᴅ.\n\n"
            "**Example:** `/song Never Gonna Give You Up` or `/song <spotify/yt link>`"
        )

    if message.reply_to_message and message.reply_to_message.text:
        query = message.reply_to_message.text.strip()
    else:
        query = message.text.split(None, 1)[1].strip()

    is_video = "vsong" in message.command[0].lower() or "vdownload" in message.command[0].lower()

    if await Spotify.valid(query):
        if "track" in query:
            mystic = await message.reply_text("🔎 **Processing Spotify Track...**")
            await process_and_send_track(client, message, mystic, query, is_video=is_video)
        elif "playlist" in query or "album" in query or "artist" in query:
            await spotify_link_auto_downloader(client, message, url=query)
        else:
            await message.reply_text("» Invalid Spotify link.")
    else:
        mystic = await message.reply_text("🔎 **Finding song, please wait...**")
        await process_and_send_track(client, message, mystic, query, is_video=is_video)
