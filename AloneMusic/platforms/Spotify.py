#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
# This file is part of < https://github.com/TheAloneTeam/AloneMusic > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/AloneMusic/blob/master/LICENSE >
#
# All rights reserved.

import asyncio
import json
import os
import re
import urllib.request

import spotipy
from py_yt import VideosSearch
from spotipy.oauth2 import SpotifyClientCredentials

import config

DOWNLOADER_BOTS = [
    "MusicsHuntersbot",
    "TopSaverBot",
    "LuxVideoBot",
    "insaverbot",
]


async def download_via_assistant_bot(url: str, chat_id: int = None):
    """
    Sends the Spotify link or query to @MusicsHuntersbot using the assistant userbot,
    downloads the audio file sent back by the bot, and returns the local file path.
    """
    try:
        from AloneMusic.utils.database import get_assistant
        ast = await get_assistant(chat_id or 1234)
        if not ast:
            return None
    except Exception:
        return None

    for bot_username in DOWNLOADER_BOTS:
        try:
            sent = await ast.send_message(bot_username, url)
            floor_id = sent.id

            clicked = False
            for _ in range(20):
                await asyncio.sleep(2)
                async for m in ast.get_chat_history(bot_username, limit=10):
                    if m.id <= floor_id:
                        continue
                    media = m.audio or m.voice or m.document or m.video
                    if media:
                        local_file = await ast.download_media(media)
                        if local_file and os.path.isfile(local_file):
                            return os.path.abspath(local_file)
                    if not clicked and m.reply_markup and getattr(m.reply_markup, "inline_keyboard", None):
                        for row in m.reply_markup.inline_keyboard:
                            for btn in row:
                                text = (btn.text or "").lower()
                                if any(x in text for x in ["audio", "mp3", "download", "🎧", "🎶"]):
                                    try:
                                        await ast.request_callback_answer(bot_username, m.id, btn.callback_data)
                                        clicked = True
                                        break
                                    except Exception:
                                        pass
                            if clicked:
                                break
        except Exception:
            continue

    return None


def _scrape_spotify(url: str):
    if "/embed/" not in url:
        embed_url = re.sub(
            r"https?://(open|music)\.spotify\.com/", "https://open.spotify.com/embed/", url
        )
    else:
        embed_url = url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
    }
    req = urllib.request.Request(embed_url, headers=headers)
    html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html
    )
    if not match:
        raise ValueError("Unable to parse Spotify data")
    data = json.loads(match.group(1))
    page_props = data.get("props", {}).get("pageProps", {})
    state = page_props.get("state", {}).get("data", {})
    entity = state.get("entity")
    if not entity:
        raise ValueError("Spotify entity not found")
    return entity


class SpotifyAPI:
    def __init__(self):
        self.regex = r"^(https:\/\/(open|music)\.spotify\.com\/)(.*)$"
        self.client_id = config.SPOTIFY_CLIENT_ID
        self.client_secret = config.SPOTIFY_CLIENT_SECRET
        if config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET:
            self.client_credentials_manager = SpotifyClientCredentials(
                self.client_id, self.client_secret
            )
            self.spotify = spotipy.Spotify(
                client_credentials_manager=self.client_credentials_manager
            )
        else:
            self.spotify = None

    async def valid(self, link: str):
        return bool(re.search(self.regex, link))

    async def download_track(self, link: str, chat_id: int = None):
        return await download_via_assistant_bot(link, chat_id)

    async def track(self, link: str):
        info = None
        if self.spotify:
            try:
                track = self.spotify.track(link)
                info = track["name"]
                for artist in track["artists"]:
                    fetched = f' {artist["name"]}'
                    if "Various Artists" not in fetched:
                        info += fetched
            except Exception:
                info = None

        if not info:
            try:
                entity = await asyncio.to_thread(_scrape_spotify, link)
                title = entity.get("title") or entity.get("name") or ""
                artists = [
                    a.get("name")
                    for a in entity.get("artists", [])
                    if a.get("name") and "Various Artists" not in a.get("name")
                ]
                if artists:
                    info = f"{title} {' '.join(artists)}"
                else:
                    subtitle = entity.get("subtitle", "")
                    info = f"{title} {subtitle}".strip()
            except Exception:
                info = link

        results = VideosSearch(info, limit=1)
        for result in (await results.next())["result"]:
            ytlink = result["link"]
            title = result["title"]
            vidid = result["id"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": ytlink,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def playlist(self, url):
        playlist_id = url.split("/")[-1].split("?")[0]
        results = []
        if self.spotify:
            try:
                playlist = self.spotify.playlist(url)
                playlist_id = playlist["id"]
                for item in playlist["tracks"]["items"]:
                    music_track = item["track"]
                    info = music_track["name"]
                    for artist in music_track["artists"]:
                        fetched = f' {artist["name"]}'
                        if "Various Artists" not in fetched:
                            info += fetched
                    results.append(info)
            except Exception:
                results = []

        if not results:
            try:
                entity = await asyncio.to_thread(_scrape_spotify, url)
                playlist_id = entity.get("id") or playlist_id
                for item in entity.get("trackList", []):
                    t_title = item.get("title", "")
                    t_sub = (item.get("subtitle") or "").replace("\xa0", " ")
                    info = f"{t_title} {t_sub}".strip()
                    if info:
                        results.append(info)
            except Exception:
                pass

        return results, playlist_id

    async def album(self, url):
        album_id = url.split("/")[-1].split("?")[0]
        results = []
        if self.spotify:
            try:
                album = self.spotify.album(url)
                album_id = album["id"]
                for item in album["tracks"]["items"]:
                    info = item["name"]
                    for artist in item["artists"]:
                        fetched = f' {artist["name"]}'
                        if "Various Artists" not in fetched:
                            info += fetched
                    results.append(info)
            except Exception:
                results = []

        if not results:
            try:
                entity = await asyncio.to_thread(_scrape_spotify, url)
                album_id = entity.get("id") or album_id
                for item in entity.get("trackList", []):
                    t_title = item.get("title", "")
                    t_sub = (item.get("subtitle") or "").replace("\xa0", " ")
                    info = f"{t_title} {t_sub}".strip()
                    if info:
                        results.append(info)
            except Exception:
                pass

        return (
            results,
            album_id,
        )

    async def artist(self, url):
        artist_id = url.split("/")[-1].split("?")[0]
        results = []
        if self.spotify:
            try:
                artistinfo = self.spotify.artist(url)
                artist_id = artistinfo["id"]
                artisttoptracks = self.spotify.artist_top_tracks(url)
                for item in artisttoptracks["tracks"]:
                    info = item["name"]
                    for artist in item["artists"]:
                        fetched = f' {artist["name"]}'
                        if "Various Artists" not in fetched:
                            info += fetched
                    results.append(info)
            except Exception:
                results = []

        if not results:
            try:
                entity = await asyncio.to_thread(_scrape_spotify, url)
                artist_id = entity.get("id") or artist_id
                for item in entity.get("trackList", []):
                    t_title = item.get("title", "")
                    t_sub = (item.get("subtitle") or "").replace("\xa0", " ")
                    info = f"{t_title} {t_sub}".strip()
                    if info:
                        results.append(info)
            except Exception:
                pass

        return results, artist_id
