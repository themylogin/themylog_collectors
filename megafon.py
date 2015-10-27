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

if storage.get("captcha", datetime.min) > datetime.now() - timedelta(hours=24):
    storage["cookies"] = {}
    raise Exception("Waiting for captcha to disappear")

page = requests.get("https://lk.megafon.ru/", cookies=storage["cookies"]).text
if "private-office-header-balans" not in page:
    csrf_request = requests.get("https://lk.megafon.ru/login/")
    if "captcha-img" in csrf_request.text:
        storage["captcha"] = datetime.now()
        raise Exception("There is captcha")

    page_request = requests.post("https://lk.megafon.ru/dologin/",
                                 cookies=csrf_request.cookies,
                                 data={"CSRF": re.search('CSRF_PARAM = "(.+)"', csrf_request.text).group(1),
                                       "j_username": "<телефон>",
                                       "j_password": "<пароль от сервис-гида>"})
    page = page_request.text
    if "captcha-img" in page:
        storage["captcha"] = datetime.now()
        raise Exception("There is captcha")

    storage["cookies"] = {cookie.name: cookie.value for cookie in page_request.cookies}

time_series = TimeSeries()
soup = BeautifulSoup(page)
time_series.balance({
    "balance":  float(re.sub(r"[^0-9\.]", "", soup.find("div", "private-office-header-balans").get_text().replace(",", "."))),
    "bonus":    float(re.sub(r"[^0-9\.]", "", soup.find("div", "private-office-width").get_text().replace(",", "."))),
})
