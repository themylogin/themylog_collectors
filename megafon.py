# -*- coding: utf-8 -*-
# crontab(minute="*/5")
# title = 'Обновление баланса Мегафон'
from __future__ import unicode_literals

from bs4 import BeautifulSoup
import datetime
import dateutil.parser
import json
import os
import re
import urllib2

from themylog.collector.time_series import TimeSeries

time_series = TimeSeries()
jsonp = urllib2.urlopen("https://sibsg.megafon.ru//WIDGET_INFO/GET_INFO?X_Username=%s&X_Password=%s&CHANNEL=WYANDEX&LANG_ID=1&P_RATE_PLAN_POS=1&P_PAYMENT_POS=2&P_ADD_SERV_POS=4&P_DISCOUNT_POS=3" % (
    "<телефон>", "<пароль от сервис-гида>",
)).read().decode("utf-8")
soup = BeautifulSoup(jsonp.replace('\\"', '"'))
time_series.balance({
    "balance":  float(re.sub(r"[^0-9\.]", "", soup.find("div", "subs_balance").get_text()).strip(".")),
    "bonus":    float(re.sub(r"[^0-9\.]", "", soup.find("div", "bonus").get_text()).strip(".")),
    "expense":  float(re.sub(r"[^0-9\.]", "", soup.find("td", "costs").get_text()).strip(".")),
    "expenses": [map(lambda td: td.get_text().strip(), tr.find_all("td"))
                 for tr in soup.find("table", "legend").find_all("tr")],
    "jsonp":    jsonp,
})
