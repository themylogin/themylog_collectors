# -*- coding: utf-8 -*-
# crontab(minute="*/5")
# title = 'Обновление баланса Мегафон'
from __future__ import unicode_literals

from bs4 import BeautifulSoup
import re
import requests

from themylog.collector.time_series import TimeSeries

time_series = TimeSeries()
csrf_request = requests.get("https://lk.megafon.ru/login/")
CSRF = re.search('CSRF_PARAM = "(.+)"', csrf_request.text).group(1)
soup = BeautifulSoup(requests.post("https://lk.megafon.ru/login/dologin/",
                                   cookies=csrf_request.cookies,
                                   data={"CSRF": CSRF,
                                         "j_username": "<телефон>",
                                         "j_password": "<пароль от сервис-гида>"}).text)
time_series.balance({
    "balance":  float(re.sub(r"[^0-9\.]", "", soup.find("div", "private-office-header-balans").get_text().replace(",", "."))),
    "bonus":    float(re.sub(r"[^0-9\.]", "", soup.find("div", "private-office-width").get_text().replace(",", "."))),
})
