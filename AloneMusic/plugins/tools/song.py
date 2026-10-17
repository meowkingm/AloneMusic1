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


@app.on_message(
    filters.command(["song", "vsong", "download", "vdownload"])
    & ~BANNED_USERS
)
async def song_download(client, message: Message):
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
    mystic = await message.reply_text("🔎 **ғɪɴᴅɪɴɢ sᴏɴɢ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...**")

    try:
        if await Spotify.valid(query):
            if "track" in query:
                details, track_id = await Spotify.track(query)
            else:
                return await mystic.edit_text("» Oɴʟʏ single sᴘᴏᴛɪғʏ track ʟɪɴᴋs ᴀʀᴇ sᴜᴘᴘᴏʀᴛᴇᴅ ғᴏʀ direct ᴅᴏᴡɴʟᴏᴀᴅ.")
        else:
            details, track_id = await YouTube.track(query)
    except Exception as e:
        return await mystic.edit_text(f"» 𝐹𝒶𝒾𝓁𝑒𝒹 to fetch song details: {e}")

    if not details or not track_id:
        return await mystic.edit_text("» sᴏɴɢ ɴᴏᴛ ғᴏᴜɴᴅ.")

    title = details.get("title", "Song")
    duration = details.get("duration_min", "0:00")
    thumb_url = details.get("thumb")
    ytlink = details.get("link", f"https://www.youtube.com/watch?v={track_id}")

    await mystic.edit_text("📥 **ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ sᴏɴɢ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...**")

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

        file_path = await YouTube.download(
            ytlink,
            mystic,
            songvideo=is_video,
            songaudio=not is_video,
            format_id=format_id,
            title=re.sub(r'[\\/*?:"<>|]', "", title)[:50],
        )

        if not file_path or not os.path.exists(file_path):
            return await mystic.edit_text("» ғᴀɪʟᴇᴅ to download the file.")

        await mystic.edit_text("📤 **ᴜᴘʟᴏᴀᴅɪɴɢ sᴏɴɢ...**")

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

        await mystic.delete()

    except Exception as e:
        await mystic.edit_text(f"» ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ: {e}")

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
