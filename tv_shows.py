# -*- coding: utf-8 -*-
# crontab(minute="*/5")
# title = "Скачивание телесериалов"
# timeout = 180
# transactional = False
from __future__ import absolute_import, division, unicode_literals

NNM_CLUB_COOKIES = b"phpbb2mysql_4_t=a%3A6%3A%7Bi%3A623486%3Bi%3A1394994292%3Bi%3A622918%3Bi%3A1394994298%3Bi%3A622716%3Bi%3A1394995519%3Bi%3A767350%3Bi%3A1395497485%3Bi%3A774862%3Bi%3A1398173986%3Bi%3A779463%3Bi%3A1398173987%3B%7D; phpbb2mysql_4_data=a%3A2%3A%7Bs%3A11%3A%22autologinid%22%3Bs%3A32%3A%22db8fddf73a3eaa51ceeb8d286eec2d5f%22%3Bs%3A6%3A%22userid%22%3Bi%3A8717806%3B%7D"
RUTRACKER_COOKIES = b"=".join(open(b"/media/storage/Torrent/.rutracker-cookies.txt").read().strip().split(b"\n")[-1].split(b"\t")[-2:])

shows = {
    #"The Big Bang Theory": {"tpb": True, "season": 9},
    #"South Park": {"tpb": True, "season": 19},
    #"Modern Family": {"tpb": True, "season": 7},
    #"Family Guy": {"tpb": True, "season": 14},
    #"Better Call Saul": {"tracker": {"urls": {"http://rutracker.org/forum/viewtopic.php?t=5172445": "1080p",
    #                                          "http://rutracker.org/forum/viewtopic.php?t=5172975": "720p"},
    #                                 "cookies": RUTRACKER_COOKIES},
    #                     "season": 2},
    #"Louie": {"tracker": {"urls": {"http://rutracker.org/forum/viewtopic.php?t=4983595": "720p"},
    #                      "cookies": RUTRACKER_COOKIES},
    #          "season": 5}
    #"Mr. Robot": {"tracker": {"urls": {"http://rutracker.org/forum/viewtopic.php?t=5015094": "720p"},
    #                          "cookies": RUTRACKER_COOKIES},
    #              "season": 1},
    #"We Bare Bears": {"tracker": {"urls": {# http://nnm-club.me/forum/viewtopic.php?t=929744
    #                                       "http://nnm-club.me/forum/download.php?id=790905": "720p"},
    #                              "cookies": NNM_CLUB_COOKIES},
    #                  "season": 1},
    #"Narcos": {"tracker": {"urls": {"http://rutracker.org/forum/viewtopic.php?t=5074619": "1080p"},
    #                       "cookies": RUTRACKER_COOKIES},
    #           "season": 1},
    #"Moonbeam City": {"tracker": {"urls": {"http://rutracker.org/forum/viewtopic.php?t=5082801": "720p"},
    #                              "cookies": RUTRACKER_COOKIES},
    #                  "season": 1},
}

import babelfish
import base64
import Cookie
from datetime import datetime, timedelta
import functools
import hashlib
import json
import logging
import lxml
import operator
import os
import random
import requests
import requesocks
import re
import shutil
import string
from subliminal import Video, download_best_subtitles, cache_region
import subprocess
import sys
import tempfile
from tpb import TPB

from themylog.client import Retriever, setup_logging_handler
from themylog.collector.timeline import Timeline
from themyutils.string import common_prefix, common_suffix

logging.getLogger("requesocks.packages.urllib3.connectionpool").setLevel(logging.ERROR)
setup_logging_handler("%s.collector" % sys.argv[1])
cache_region.configure("dogpile.cache.memory")


class DelugeClient(object):
    def __init__(self, url, password):
        self.url = url
        self.password = password

        self.session = requests.Session()
        self.authorized = False

    def call(self, method, *args):
        if not self.authorized:
            if not self.do_call("auth.login", self.password):
                raise Exception("Ошибка авторизации")
            if not self.do_call("web.connected"):
                raise Exception("Deluge Web UI не подключен к серверу")
            self.authorized = True

        return self.do_call(method, *args)

    def do_call(self, method, *args):
        logging.getLogger("deluge").debug("Calling %r%r", method, args)

        result = self.session.post("%s/json" % self.url,
                                   data=json.dumps({"id": 1,
                                                    "method": method,
                                                    "params": args}),
                                   headers={"Accept": "application/json",
                                            "Content-Type": "application/json"}).json()
        if result["error"] is not None:
            raise Exception("Ошибка вызова %s: %s" % (method, result["error"]))

        logging.getLogger("deluge").debug("Result: %r", result["result"])
        return result["result"]


def _subliminal(args):
    video = Video.fromname(args["old_name"])
    languages = {babelfish.Language.fromietf("en")}
    subtitles = []
    for hearing_impaired in [True, False]:
        subtitles += download_best_subtitles({video}, languages, hearing_impaired=hearing_impaired).get(video, [])

    for subtitle in sorted(subtitles, key=lambda s: s.compute_score(video), reverse=True):
        open(os.path.splitext(args["path"])[0] + ".%s.srt" % subtitle.language, "w").write(subtitle.text.encode("utf-8"))
        return True


tpb = TPB("http://thepiratebay.se")
qualities = ("1080p", "720p", "")
video_extensions = (".avi", ".mkv", ".mp4")
subtitle_providers = {"subliminal": _subliminal}

torrent_file_seeker = Timeline("torrent_file_seeker")
torrent_downloader = Timeline("torrent_downloader")

deluge = DelugeClient("<путь к deluge web ui>", "<пароль>")
downloads = "/media/storage/Torrent/downloads"
tmp = "/media/storage/Torrent/.tmp"


def make_title(show, season, episode, quality):
    return " ".join(filter(None, [show, "S%02dE%02d" % (season, episode), quality]))


def make_torrent_location(show, season, quality, url):
    return os.path.join(downloads, make_torrent_title(show, season, quality, url))


def make_torrent_title(show, season, quality, url):
    return " ".join(filter(None, [show, "S%02d" % season, quality, hashlib.md5(url).hexdigest()[:6]]))


def find_video_files(dst):
    video_files = {}
    for root, dirs, files in os.walk(dst.encode("utf-8")):
        for file in files:
            if file.decode("utf-8").lower().endswith(video_extensions):
                path = os.path.join(root, file)
                video_files[path.decode("utf-8")] = os.path.getsize(path)
    return video_files


found_torrents = []
store_torrents = []
for show, config in shows.iteritems():
    if config.get("tpb"):
        try:
            torrents = list(tpb.search(show, order=99))
        except lxml.etree.XMLSyntaxError:
            logging.getLogger("tpb").warning("Unable to open thepiratebay", exc_info=True)
            continue

        for torrent in torrents:
            logging.getLogger("tpb").debug("Found torrent %s", torrent.url)

            if torrent.seeders < 100:
                logging.getLogger("tpb").debug("Torrent has %d seeders, skipping", torrent.seeders)
                continue

            s_e_match = re.search(r"S(?P<season>[0-9]+)E(?P<episode>[0-9]+)", torrent.title, flags=re.IGNORECASE)
            if s_e_match is None:
                logging.getLogger("tpb").debug("Unable to parse torrent title '%s', skipping", torrent.title)
                continue

            season = int(s_e_match.group("season"))
            episode = int(s_e_match.group("episode"))

            if config.get("season") and config.get("season") != season:
                continue

            for test_quality in qualities:
                if test_quality in torrent.title:
                    quality = test_quality
                    break
            else:
                quality = ""

            title_for_quality = functools.partial(make_title, show, season, episode)

            if not any(torrent_file_seeker.contains(title_for_quality(test_quality)) for test_quality in qualities
                       if qualities.index(test_quality) <= qualities.index(quality)):
                try:
                    d = tempfile.mkdtemp()
                    subprocess.check_call(["timeout", "30", "aria2c", "--bt-metadata-only=true",
                                           "--bt-save-metadata=true", "-d", d, torrent.magnet_link])
                    output = subprocess.check_output(["aria2c", "-S", os.path.join(d, os.listdir(d)[0])])
                    for file in output.split("\n"):
                        if re.match("[0-9 ]+\|.+", file):
                            if file.lower().endswith(video_extensions):
                                break
                    else:
                        logging.getLogger("tpb").debug("Torrent has no video files: %r", torrent.files)
                        continue
                except Exception:
                    logging.getLogger("tpb").warning("Unable to load files", exc_info=True)
                    continue

                tmp_dst = os.path.join(tmp, "".join(random.choice(string.ascii_letters + string.digits)
                                                    for _ in range(32)))
                found_torrents.append((torrent.magnet_link, tmp_dst))

                store_torrents.append((title_for_quality(quality),
                                       {"show": show,
                                        "season": season,
                                        "episode": episode,
                                        "quality": quality,
                                        "tmp_dst": tmp_dst,
                                        "tpb": torrent.__dict__},
                                        "Начато скачивание %s" % title_for_quality(quality)))

    if config.get("tracker"):
        tracker = config["tracker"]
        season = config["season"]
        for url, quality in tracker["urls"].items():
            cookies = {k: v.value for k, v in Cookie.SimpleCookie(tracker["cookies"]).items()}
            try:
                if url.startswith("http://rutracker.org/"):
                    session = requesocks.session()
                    session.proxies = {'http': 'socks5://127.0.0.1:9050',
                                       'https': 'socks5://127.0.0.1:9050'}
                    r = session.post(url.replace("http://", "http://dl.").replace("viewtopic.php", "dl.php"),
                                     headers={"Referer": url}, cookies=cookies).content
                else:
                    r = requests.get(url, cookies=cookies).content
            except Exception:
                logging.getLogger("tracker").warning("Unable to download torrent", exc_info=True)
                continue

            location = make_torrent_location(show, season, quality, url)
            found_torrents.append((base64.b64encode(r), location))

for torrent, download_location in found_torrents:
    if not os.path.exists(download_location.encode("utf-8")):
        os.mkdir(download_location.encode("utf-8"))

    deluge.call("webapi.add_torrent", torrent, {"download_location": download_location})

for key, args, explanation in store_torrents:
    torrent_file_seeker.store(key, args, explanation=explanation)


torrents_dict = deluge.call("webapi.get_torrents", None, ["progress", "save_path", "time_added"])["torrents"]
torrents = {torrent["save_path"]: torrent_id
            for torrent_id, torrent in torrents_dict.iteritems()
            if torrent["progress"] == 100}
for downloading in Retriever().retrieve(
        (operator.and_,
         (operator.eq, lambda k: k("application"), torrent_file_seeker.application),
         (operator.and_,
          (operator.eq, lambda k: k("logger"), torrent_file_seeker.logger),
          (operator.gt, lambda k: k("datetime"), datetime.now() - timedelta(days=7))))):
    if downloading.args["tmp_dst"] in torrents:
        video_files = find_video_files(downloading.args["tmp_dst"])
        if video_files:
            video_file = sorted(video_files.items(), key=lambda (path, size): -size)[0][0]

            new_dir = os.path.join(downloads, downloading.args["show"])
            new_name = make_title(downloading.args["show"],
                                  downloading.args["season"],
                                  downloading.args["episode"],
                                  downloading.args["quality"]) + os.path.splitext(video_file)[1]
            new_path = os.path.join(new_dir, new_name)

            if not os.path.exists(new_dir):
                os.makedirs(new_dir)
            os.rename(video_file.encode("utf-8"), new_path)

            deluge.call("webapi.remove_torrent", torrents[downloading.args["tmp_dst"]])
            shutil.rmtree(downloading.args["tmp_dst"])

            torrent_downloader.store(make_title(downloading.args["show"],
                                                downloading.args["season"],
                                                downloading.args["episode"],
                                                downloading.args["quality"]),
                                     {"show": downloading.args["show"],
                                      "season": downloading.args["season"],
                                      "episode": downloading.args["episode"],
                                      "quality": downloading.args["quality"],
                                      "old_name": os.path.split(video_file)[-1],
                                      "path": new_path},
                                     explanation="Завершено скачивание %s" % make_title(downloading.args["show"],
                                                                                        downloading.args["season"],
                                                                                        downloading.args["episode"],
                                                                                        downloading.args["quality"]))

for show, config in shows.iteritems():
    if config.get("tracker"):
        tracker = config["tracker"]
        season = config["season"]
        for url, quality in tracker["urls"].items():
            location = make_torrent_location(show, season, quality, url)
            if location in torrents:
                video_files = find_video_files(location).keys()
                prefix = common_prefix(video_files)
                suffix = common_suffix(video_files)
                for video_file in video_files:
                    try:
                        episode = Video.fromname(video_file).episode
                    except:
                        if len(video_files) == 1:
                            episode = 1
                        else:
                            episode = video_file.replace(prefix, "").replace(suffix, "")
                            try:
                                episode = int(episode)
                            except ValueError:
                                pass
                    msg = "%s %s" % (make_torrent_title(show, season, quality, url), episode)
                    downloaded = Retriever().retrieve(
                        (operator.and_,
                         (operator.eq, lambda k: k("application"), torrent_downloader.application),
                         (operator.and_,
                          (operator.eq, lambda k: k("logger"), torrent_downloader.logger),
                          (operator.eq, lambda k: k("msg"), msg))))
                    if not downloaded:
                        torrent_downloader.store(msg,
                                                 {"show": show,
                                                  "season": season,
                                                  "episode": episode,
                                                  "quality": quality,
                                                  "old_name": video_file,
                                                  "path": video_file},
                                                 explanation="Завершено скачивание %s" % msg)

                for torrent_id in sorted([torrent_id
                                          for torrent_id, torrent in torrents_dict.iteritems()
                                          if torrent["save_path"] == location],
                                         key=lambda torrent_id: torrents_dict[torrent_id]["time_added"])[:-1]:
                    deluge.call("webapi.remove_torrent", torrent_id)


subtitle_downloaders = {name: Timeline("%s_subtitle_provider" % name) for name in subtitle_providers}
for downloaded in Retriever().retrieve(
        (operator.and_,
         (operator.eq, lambda k: k("application"), torrent_downloader.application),
         (operator.and_,
          (operator.eq, lambda k: k("logger"), torrent_downloader.logger),
          (operator.gt, lambda k: k("datetime"), datetime.now() - timedelta(days=14))))):
    if not isinstance(downloaded.args["episode"], int):
        continue

    if downloaded.args["show"].encode("ascii", "ignore") != downloaded.args["show"]:
        logging.getLogger("subtitle_downloader").debug("Show %s is not ASCII, skipping", downloaded.args["show"])
        continue

    for name, provider in subtitle_providers.items():
        subtitle_downloader = subtitle_downloaders[name]
        if not subtitle_downloader.contains(downloaded.msg):
            try:
                data = provider(downloaded.args)
            except:
                logging.getLogger("subtitle_provider.%s" % name).warning("Unable to download subtitles", exc_info=True)
                continue

            if data:
                subtitle_downloader.store(downloaded.msg, {"show": downloaded.args["show"],
                                                           "season": downloaded.args["season"],
                                                           "episode": downloaded.args["episode"],
                                                           "quality": downloaded.args["quality"],
                                                           "data": data},
                                          explanation="Скачаны субтитры %s к %s" % (
                                              name, make_title(downloaded.args["show"],
                                                               downloaded.args["season"],
                                                               downloaded.args["episode"],
                                                               downloaded.args["quality"])
                                          ))
