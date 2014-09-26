# -*- coding: utf-8 -*-
# crontab(minute="*/5")
# title = 'Обновление баланса транспортной карты'
from __future__ import unicode_literals

import datetime
import dateutil.parser
import json
import os
import urllib2

from themylog.collector.timeline import Timeline
from themylog.collector.time_series import TimeSeries

timeline = Timeline(logger="trips")
opener = urllib2.build_opener()
opener.addheaders.append(("Cookie", "ASP.NET_SessionId=%(session_id)s; tcard_ek_pan=%(card_number)s" % {
    "session_id"    : "<ID сессии>",
    "card_number"   : "<номер транспортной карты>",
}))
trips_history = json.loads(opener.open("https://t-karta.ru/ek/SitePages/TransportServicePage.aspx?functionName=GetCardTripsHistory&pan=%(pan)s&dateFrom=%(dateFrom)s&dateTo=%(dateTo)s" % {
    "pan"           : "<номер транспортной карты>",
    "dateFrom"      : (datetime.datetime.now() - datetime.timedelta(days=13)).strftime("%d.%m.%Y"),
    "dateTo"        : datetime.datetime.now().strftime("%d.%m.%Y"),
}).read())["TripsHistory"]
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
info = json.loads(opener.open("https://t-karta.ru/ek/SitePages/TransportServicePage.aspx?functionName=GetCardInfo&pan=%(pan)s&dateFrom=%(dateFrom)s&dateTo=%(dateTo)s" % {
    "pan"           : "<номер транспортной карты>",
    "dateFrom"      : (datetime.datetime.now() - datetime.timedelta(days=13)).strftime("%d.%m.%Y"),
    "dateTo"        : datetime.datetime.now().strftime("%d.%m.%Y"),
}).read())
time_series.balance(info["CardSum"] / 100, logger="balance")
