# -*- coding: utf-8 -*-
# crontab(minute="*/5")
# title = "Скачивание телесериалов"
# timeout = 180
from __future__ import absolute_import, division, unicode_literals

shows = {
    "The Big Bang Theory": {"tpb": True, "season": 8},
    "South Park": {"tpb": True, "season": 18},
    "Modern Family": {"tpb": True, "season": 6},
}

import babelfish
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import functools
import json
import logging
import lxml
import operator
import os
import random
import requests
import re
import shutil
import string
from subliminal import Video, download_best_subtitles
import sys
from tpb import TPB

from themylog.client import Retriever, setup_logging_handler
from themylog.collector.timeline import Timeline

setup_logging_handler("%s.collector" % sys.argv[1])


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
        result = self.session.post("%s/json" % self.url,
                                   data=json.dumps({"id": 1,
                                                    "method": method,
                                                    "params": args}),
                                   headers={"Accept": "application/json",
                                            "Content-Type": "application/json"}).json()
        if result["error"] is not None:
            raise Exception("Ошибка вызова %s: %s" % (method, result["error"]))

        return result["result"]


def _subliminal(args):
    subtitles = download_best_subtitles([Video.fromname(args["old_name"])],
                                        {babelfish.Language.fromietf("en")}).values()[0]
    for subtitle in subtitles:
        open(os.path.splitext(args["path"])[0] + ".%s.srt" % subtitle.language, "w").write(subtitle.text.encode("utf-8"))
    if subtitles:
        return True


def notabenoid(args):
    search = BeautifulSoup(requests.get("http://notabenoid.com/search", params={"t": str(args["show"])}).text)
    for li in search.select(".search-results li"):
        if "субтитры с английского на русский" in unicode(li):
            a = li.select("p a")[0]
            if (re.search("%d (сезон|season)" % args["season"], unicode(a).lower()) or
                re.search("(сезон|season) 0?%d" % args["season"], unicode(a).lower())):
                page = BeautifulSoup(requests.get("http://notabenoid.com" + a.attrs["href"]).text)
                for tr in page.select("#Chapters tbody tr"):
                    t = tr.select(".t")[0]
                    if re.search("(e|x)%02d" % args["episode"], unicode(t).lower()):
                        if float(tr.select(".r")[0].get_text().strip().split(" ")[0].replace("%", "")) >= 95:
                            link = "http://notabenoid.com" + tr.select(".act")[0].attrs["href"]
                            link = link.replace("/ready",
                                                "/download?algorithm=0&skip_neg=0&author_id=0&format=s&enc=UTF-8&crlf=0")
                            response = requests.get(link).text.encode("utf-8")
                            open(os.path.splitext(args["path"])[0] + ".ru.srt", "w").write(response)
                            return True


tpb = TPB("http://thepiratebay.se")
qualities = ("1080p", "720p", "")
video_extensions = (".avi", ".mkv", ".mp4", ".wmv")
subtitle_providers = {"subliminal": _subliminal, "notabenoid": notabenoid}

torrent_file_seeker = Timeline("torrent_file_seeker")
torrent_downloader = Timeline("torrent_downloader")

deluge = DelugeClient("<путь к deluge web ui>", "<пароль>")
downloads = "/media/storage/Torrent/downloads"
tmp = "/media/storage/Torrent/.tmp"


def make_title(show, season, episode, quality):
    return " ".join(filter(None, [show, "S%02dE%02d" % (season, episode), quality]))


for show, config in shows.iteritems():
    if config.get("tpb"):
        try:
            torrents = list(tpb.search(show, order=99))
        except lxml.etree.XMLSyntaxError:
            logging.getLogger("tpb").exception("Unable to open thepiratebay")
            continue

        for torrent in torrents:
            s_e_match = re.search(r"S(?P<season>[0-9]+)E(?P<episode>[0-9]+)", torrent.title, flags=re.IGNORECASE)
            if s_e_match is None:
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
                tmp_dst = os.path.join(tmp, "".join(random.choice(string.ascii_letters + string.digits)
                                                    for _ in range(32)))
                os.mkdir(tmp_dst)

                deluge.call("webapi.add_torrent", torrent.magnet_link, {"download_location": tmp_dst})

                torrent_file_seeker.store(title_for_quality(quality),
                                          {"show": show,
                                           "season": season,
                                           "episode": episode,
                                           "quality": quality,
                                           "tmp_dst": tmp_dst,
                                           "tpb": torrent.__dict__},
                                          explanation="Начато скачивание %s" % title_for_quality(quality))


torrents = {torrent["save_path"]: torrent_id
            for torrent_id, torrent in deluge.call("webapi.get_torrents", None,
                                                   ["save_path", "progress"])["torrents"].iteritems()
            if torrent["progress"] == 100}
for downloading in Retriever().retrieve(
        (operator.and_,
         (operator.eq, lambda k: k("application"), torrent_file_seeker.application),
         (operator.and_,
          (operator.eq, lambda k: k("logger"), torrent_file_seeker.logger),
          (operator.gt, lambda k: k("datetime"), datetime.now() - timedelta(days=1))))):
    if downloading.args["tmp_dst"] in torrents:
        video_files = {}
        for root, dirs, files in os.walk(downloading.args["tmp_dst"]):
            for file in files:
                if file.lower().endswith(video_extensions):
                    path = os.path.join(root, file)
                    video_files[path] = os.path.getsize(path)
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
            os.rename(video_file, new_path)

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


subtitle_downloaders = {name: Timeline("%s_subtitle_provider" % name) for name in subtitle_providers}
for downloaded in Retriever().retrieve(
        (operator.and_,
         (operator.eq, lambda k: k("application"), torrent_downloader.application),
         (operator.and_,
          (operator.eq, lambda k: k("logger"), torrent_downloader.logger),
          (operator.gt, lambda k: k("datetime"), datetime.now() - timedelta(days=14))))):
    for name, provider in subtitle_providers.items():
        subtitle_downloader = subtitle_downloaders[name]
        if not subtitle_downloader.contains(downloaded.msg):
            try:
                data = provider(downloaded.args)
            except:
                logging.getLogger("subtitle_provider.%s" % name).exception("Unable to download subtitles")
                continue

            if data:
                subtitle_downloader.store(downloaded.msg, {"show": downloading.args["show"],
                                                           "season": downloading.args["season"],
                                                           "episode": downloading.args["episode"],
                                                           "quality": downloading.args["quality"],
                                                           "data": data},
                                          explanation="Скачаны субтитры %s к %s" % (
                                              name, make_title(downloaded.args["show"],
                                                               downloaded.args["season"],
                                                               downloaded.args["episode"],
                                                               downloaded.args["quality"])
                                          ))
