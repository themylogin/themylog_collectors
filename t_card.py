# -*- coding: utf-8 -*-
# crontab(minute="*/5")
# title = 'Обновление баланса транспортной карты'
from __future__ import unicode_literals

import datetime
import dateutil.parser
import json
import re
import requests

from themylog.collector.timeline import Timeline
from themylog.collector.time_series import TimeSeries

timeline = Timeline(logger="trips")
cookies = {"UserCity": "Novosibirsk",
           "ASP.NET_SessionId": "<ID сессии>"}
proxies = {"https": "proxy"}
trips_history = json.loads(requests.post("https://t-karta.ru/EK/Cabinet/TripHistory/", cookies=cookies, proxies=proxies, data={
    "pan"           : "<номер транспортной карты>",
    "dateFrom"      : (datetime.datetime.now() - datetime.timedelta(days=13)).strftime("%d.%m.%Y"),
    "dateTo"        : datetime.datetime.now().strftime("%d.%m.%Y"),
}).json())["TripsHistory"]
if trips_history:
    for trip in trips_history:
        if timeline.contains(trip["Time"]):
            continue

        timeline.store(trip["Time"], {
            "route":        trip["RouteNum"],
            "transport":    trip["RouteType"],
            "company":      trip["CompanyName"],
            "amount":       trip["Summa"],
        }, datetime=dateutil.parser.parse(trip["Time"], dayfirst=True))

time_series = TimeSeries()
info = json.loads(re.search(r"var card = (\{.+\});",
                            requests.get("https://t-karta.ru/EK/Cabinet/Trip", cookies=cookies, proxies=proxies).text).group(1))
time_series.balance(info["CardSum"] / 100, logger="balance")
