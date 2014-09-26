# -*- coding: utf-8 -*-
# crontab(minute="*/15")
# title = 'Обновление погоды'
from __future__ import unicode_literals

from bs4 import BeautifulSoup
import urllib

from themylog.collector.time_series import TimeSeries

ngs = BeautifulSoup(urllib.urlopen("http://pogoda.ngs.ru").read())

temperature_div = ngs.find("div", "today-panel__temperature")

ts = TimeSeries()
ts.weather({
    "temperature":          "%s°C" % temperature_div.find("span", "value__main").get_text().strip().replace(" ", ""),
    "temperature_trend":    "+" if temperature_div.find("i", "icon-temp_status-up") else "-",

    "description" :         temperature_div.find("span", "value-description").get_text().strip().lower(),
    "romance":              "Восход: %s, закат: %s" % tuple(ngs.find_all("div", "today-panel__info__main__item")[1].\
                                                                find_all("dt")[0].\
                                                                get_text().\
                                                                strip().\
                                                                split(" − ")),
})
