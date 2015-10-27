# -*- coding: utf-8 -*-
# crontab(minute="*/5")
# title = 'Обновление баланса транспортной карты'
from __future__ import unicode_literals

import datetime
import dateutil.parser
import json
import os
import PIL.Image
import re
import requests
import subprocess
import tempfile

from themylog.collector.timeline import Timeline
from themylog.collector.time_series import TimeSeries
from themylog.collector.utils.storage import Storage

PAN = "<номер транспортной карты>"

storage = Storage()
timeline = Timeline(logger="trips")
time_series = TimeSeries()

session = requests.Session()
session.get("https://t-karta.ru/Events/Novosibirsk").content

info = json.loads(re.search(r"var card = (\{.+\});",
                            session.post("https://t-karta.ru/EK/Cabinet/Trip",
                                         data={"pan": PAN,
                                               "currDate": datetime.datetime.now().strftime("%d.%m.%Y")}).text).group(1))
time_series.balance(info["CardSum"] / 100, logger="balance")

trips_history = json.loads(session.post("https://t-karta.ru/EK/Cabinet/TripHistory/", data={
    "pan"           : PAN,
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

import sys
sys.exit(0)


def get_info():
    return re.search(r"var card = (\{.+\});",
                     requests.get("https://t-karta.ru/EK/Cabinet/Trip", cookies=storage.get("cookies", None)).text)

info = get_info()
if info is None:
    tmp_dir = tempfile.mkdtemp()

    login_request = requests.get("https://t-karta.ru/Events/Novosibirsk")
    captcha_path = re.search(r"/Content/capcha/CaptchaImage\.(.+)\.jpg", login_request.text).group(0)
    local_captcha_path = os.path.join(tmp_dir, "captcha.jpg")
    with open(local_captcha_path, "w") as f:
        f.write(requests.get("https://t-karta.ru" + captcha_path).content)

    captcha = PIL.Image.open(local_captcha_path).resize((360, 100)).convert("1")
    width, height = captcha.size
    data = captcha.load()
    chop = 2

    # Iterate through the rows.
    for y in range(height):
        for x in range(width):

            # Make sure we're on a dark pixel.
            if data[x, y] > 128:
                continue

            # Keep a total of non-white contiguous pixels.
            total = 0

            # Check a sequence ranging from x to image.width.
            for c in range(x, width):

                # If the pixel is dark, add it to the total.
                if data[c, y] < 128:
                    total += 1

                # If the pixel is light, stop the sequence.
                else:
                    break

            # If the total is less than the chop, replace everything with white.
            if total <= chop:
                for c in range(total):
                    data[x + c, y] = 255

            # Skip this sequence we just altered.
            x += total


    # Iterate through the columns.
    for x in range(width):
        for y in range(height):

            # Make sure we're on a dark pixel.
            if data[x, y] > 128:
                continue

            # Keep a total of non-white contiguous pixels.
            total = 0

            # Check a sequence ranging from y to image.height.
            for c in range(y, height):

                # If the pixel is dark, add it to the total.
                if data[x, c] < 128:
                    total += 1

                # If the pixel is light, stop the sequence.
                else:
                    break

            # If the total is less than the chop, replace everything with white.
            if total <= chop:
                for c in range(total):
                    data[x, y + c] = 255

            # Skip this sequence we just altered.
            y += total

    text = ""
    for i in range(4):
        letter_path = os.path.join(tmp_dir, "%d.png" % i)
        captcha.crop((width / 4 * i, 0, width / 4 * (i + 1) - 1, height - 1)).save(letter_path)
        letter = subprocess.check_output(["tesseract", letter_path, "stdout", "-psm", "10"]).strip().upper()
        if len(letter) != 1:
            raise Exception("%r is not a letter" % letter)
        text += letter

    login_request = requests.post("https://t-karta.ru/EK/Cabinet/CheckUserCard",
                                  data={"pan": PAN,
                                        "currDate": datetime.datetime.now("%d.%m.%Y")},
                                  cookies=login_request.cookies)
    storage["cookies"] = {cookie.name: cookie.value for cookie in login_request.cookies}

    info = get_info()
    if info is None:
        raise Exception("Login failed")
