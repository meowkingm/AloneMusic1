#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/AloneMusic > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/AloneMusic/blob/master/LICENSE >
#
# All rights reserved.

import asyncio

from AloneMusic import YouTube, app
from AloneMusic.core.call import autoplay_in_progress, fetch_artist_tracks, upcoming_message
from AloneMusic.misc import db
from AloneMusic.utils.database import get_active_chats, get_autoplay, is_music_playing
from AloneMusic.utils.stream.queue import put_queue


async def pre_download_track(vidid: str):
    try:
        await YouTube.download(vidid, None, videoid=True, video=False)
    except Exception:
        pass


async def timer():
    while not await asyncio.sleep(1):
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            if not await is_music_playing(chat_id):
                continue
            playing = db.get(chat_id)
            if not playing:
                continue
            duration = int(playing[0]["seconds"])
            if duration == 0:
                continue
            if db[chat_id][0]["played"] >= duration:
                continue
            db[chat_id][0]["played"] += 1

            if len(playing) > 1:
                next_item = playing[1]
                next_vid = next_item.get("vidid")
                if next_vid and "vid_" in next_item.get("file", "") and not next_item.get("pre_downloaded"):
                    next_item["pre_downloaded"] = True
                    asyncio.create_task(pre_download_track(next_vid))

            played = db[chat_id][0]["played"]
            if duration - played == 10 and not db[chat_id][0].get("notified_10s"):
                db[chat_id][0]["notified_10s"] = True

                if len(playing) == 1 and await get_autoplay(chat_id) and not autoplay_in_progress.get(chat_id):
                    curr = playing[0]
                    artist_name = curr.get("artist")
                    if not artist_name:
                        t_title = curr.get("title", "")
                        if " - " in t_title:
                            artist_name = t_title.split(" - ")[0].strip()
                        elif " " in t_title:
                            artist_name = t_title.split()[0].strip()
                        else:
                            artist_name = t_title.strip()
                    curr_vidid = curr.get("vidid")
                    artist_tracks = await fetch_artist_tracks(artist_name, curr_vidid, chat_id)
                    if artist_tracks:
                        autoplay_in_progress[chat_id] = True
                        user_by = curr.get("by", "Autoplay")
                        user_id = curr.get("user_id", 0)
                        orig_cid = curr.get("chat_id", chat_id)
                        for trk in artist_tracks:
                            vidid = trk.get("vidid")
                            title = trk.get("title")
                            dur_min = trk.get("duration_min", "03:00")
                            await put_queue(
                                chat_id,
                                orig_cid,
                                f"vid_{vidid}",
                                title,
                                dur_min,
                                user_by,
                                vidid,
                                user_id,
                                "audio",
                                artist=artist_name,
                            )

                next_title = None
                if len(playing) > 1:
                    next_item = playing[1]
                    next_title = next_item.get("title")
                    next_vid = next_item.get("vidid")
                    if next_vid and "vid_" in next_item.get("file", ""):
                        asyncio.create_task(pre_download_track(next_vid))

                if next_title:
                    try:
                        orig_cid = playing[0].get("chat_id", chat_id)
                        msg = await app.send_message(
                            orig_cid,
                            f"⌛ <b>Nᴇxᴛ Sᴏɴɢ Pʟᴀʏɪɴɢ Iɴ 10s :</b>\n\n🎵 <b>{next_title}</b>",
                        )
                        upcoming_message[chat_id] = msg
                    except Exception:
                        pass


try:
    asyncio.create_task(timer())
except RuntimeError:
    pass
