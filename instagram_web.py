# -*- coding: utf-8 -*-
# crontab(minute="*/10")
# title = "Обновление Instagram"
# timeout = 12000
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
import json
import re
import requests
import sys
import textwrap

from themylog.collector.timeline import Timeline

session = requests.Session()
session.get("https://www.instagram.com/")
headers = {"x-instagram-ajax": "1",
           "x-requestes-with": "XMLHttpRequest",
           "referer": "https://www.instagram.com/",
           "authority": "www.instagram.com",
           "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36"}

headers["x-csrftoken"] = session.cookies["csrftoken"]
session.post("https://www.instagram.com/accounts/login/ajax/",
             headers=headers,
             data={"username": "<username>",
                   "password": "<password>"})

shared_data = json.loads(re.search('window._sharedData = (.+);<', session.get("https://www.instagram.com/themylogin/").text).group(1))
user_id = int(shared_data["config"]["viewer"]["id"])
cursor = int(shared_data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"][0]["id"]) + 1

timeline = Timeline()
while True:
    headers["x-csrftoken"] = session.cookies["csrftoken"]
    data = session.post("https://www.instagram.com/query/",
                        headers=headers,
                        data={
                            "q": textwrap.dedent("""\
                                    ig_user(%d) { media.after(%d, 12) {
                                      count,
                                      nodes {
                                        caption,
                                        code,
                                        comments {
                                          count
                                        },
                                        comments_disabled,
                                        date,
                                        dimensions {
                                          height,
                                          width
                                        },
                                        display_src,
                                        id,
                                        is_video,
                                        likes {
                                          count
                                        },
                                        owner {
                                          id
                                        },
                                        thumbnail_src,
                                        video_views
                                      },
                                      page_info
                                    }
                                     }\
                            """ % (user_id, cursor)),
                            "ref": "users::show",
                        }).json()
    if not data["media"]["nodes"]:
        sys.exit(0)
    for media in data["media"]["nodes"]:
        if timeline.contains(media["id"]):
            sys.exit(0)

        cursor = int(media["id"])

        timeline.store(media["id"], media, datetime=datetime.utcfromtimestamp(media["date"]))

        requests.get("http://thelogin.ru/data/internet/%s" % media["display_src"].replace("://", "/")).raise_for_status()
        requests.get("http://thelogin.ru/data/internet/%s" % media["thumbnail_src"].replace("://", "/")).raise_for_status()