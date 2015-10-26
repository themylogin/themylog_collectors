# -*- coding: utf-8 -*-
# crontab(minute="*/5")
# title = 'Обновление баланса Мегафон'
from __future__ import unicode_literals

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import requests

from themylog.collector.time_series import TimeSeries
from themylog.collector.utils.storage import Storage

storage = Storage()

if storage.get("captcha", datetime.min) > datetime.now() - timedelta(hours=2):
    raise Exception("Waiting for captcha to disappear")

try:
    page = requests.get("https://lk.megafon.ru/", cookies=storage["cookies"]).text
    if "private-office-header-balans" not in page.text:
        raise Exception("Not authorized")
except Exception:
    csrf_request = requests.get("https://lk.megafon.ru/login/")
    if "captcha-img" in csrf_request.text:
        storage["captcha"] = datetime.now()
        raise Exception("There is captcha")

    page = requests.post("https://lk.megafon.ru/dologin/",
                         cookies=csrf_request.cookies,
                         data={"CSRF": re.search('CSRF_PARAM = "(.+)"', csrf_request.text).group(1),
                               "j_username": "<телефон>",
                               "j_password": "<пароль от сервис-гида>"}).text
    if "captcha-img" in page:
        storage["captcha"] = datetime.now()
        raise Exception("There is captcha")

    storage["cookies"] = {cookie.name: cookie.value for cookie in csrf_request.cookies}

time_series = TimeSeries()
soup = BeautifulSoup(page)
time_series.balance({
    "balance":  float(re.sub(r"[^0-9\.]", "", soup.find("div", "private-office-header-balans").get_text().replace(",", "."))),
    "bonus":    float(re.sub(r"[^0-9\.]", "", soup.find("div", "private-office-width").get_text().replace(",", "."))),
})
