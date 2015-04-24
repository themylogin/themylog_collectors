# -*- coding: utf-8 -*-
# crontab(minute="*/10")
# title = "Обновление Instagram"
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
import instagram
import sys
import urlparse

from themyutils.datetime import utc_to_local

from themylog.collector.timeline import Timeline

instagram_api = instagram.InstagramAPI(access_token=b"<access token>",
                                       client_secret=b"<client secret>")

timeline = Timeline()
max_id = None
while True:
    recent_media, next_ = instagram_api.user_recent_media(user_id=b"249094559", max_id=max_id, count=10, return_json=True)

    for media in recent_media:
        if timeline.contains(media["id"]):
            sys.exit(0)

        timeline.store(media["id"], media, datetime=utc_to_local(datetime.utcfromtimestamp(float(media["created_time"]))))

    if next_:
        max_id = urlparse.parse_qs(urlparse.urlparse(next_).query)["max_id"][0]
    else:
        sys.exit(0)
