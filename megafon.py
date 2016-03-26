# -*- coding: utf-8 -*-
# crontab(minute="*/5")
# title = 'Обновление баланса Мегафон'
from __future__ import unicode_literals

from bs4 import BeautifulSoup
from captcha2upload import CaptchaUpload
import logging
import re
import requests
import sys
import tempfile

from themyutils.requests import chrome

from themylog.client import setup_logging_handler
from themylog.collector.time_series import TimeSeries
from themylog.collector.utils.storage import Storage

setup_logging_handler("%s.collector" % sys.argv[1])

storage = Storage()

headers = {"User-Agent": chrome}

response = requests.get("https://lk.megafon.ru/",
                        headers=headers,
                        cookies=storage.get("cookie", None))
if "Сервис временно недоступен" in response.text:
    raise Exception("Сервис временно недоступен")
if "/login/" in response.url:
    csrf_request = response
    auth_data = data={"CSRF": re.search('CSRF_PARAM = "(.+)"', csrf_request.text).group(1),
                      "j_username": "<телефон>",
                      "j_password": "<пароль от сервис-гида>"}

    soup = BeautifulSoup(csrf_request.text)
    captcha = soup.find("img", "captcha-img")
    if captcha:
        captcha_request = requests.get("https://lk.megafon.ru" + captcha["src"],
                                       headers=headers,
                                       cookies=csrf_request.cookies)
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            f.write(captcha_request.content)
            f.flush()

            captcha = CaptchaUpload("<2captcha.com key>", logging.getLogger("captcha"), 30)
            auth_data["captcha"] = captcha.solve(f.name)

    page_request = requests.post("https://lk.megafon.ru/dologin/",
                                 headers=headers,
                                 cookies=csrf_request.cookies,
                                 data=auth_data)
    page = page_request.text
    if "captcha-img" in page:
        raise Exception("Captcha was solved incorrectly")

    storage["cookies"] = {cookie.name: cookie.value for cookie in page_request.cookies}
else:
    page = response.text

time_series = TimeSeries()
soup = BeautifulSoup(page)
time_series.balance({
    "balance":  float(re.sub(r"[^\-0-9\.]", "", soup(text=re.compile("Баланс"))[0].next.get_text().replace(",", ".").replace("−", "-"))),
    "bonus":    float(re.sub(r"[^0-9\.]", "", soup.find("div", "private-office-width").get_text().replace(",", "."))),
})
