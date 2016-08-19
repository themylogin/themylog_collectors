# -*- coding: utf-8 -*-
# crontab(minute="*/10")
# title = "Обновление карты «Перекрёсток»"
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
import json
import requests
import sys
import time

from themylog.collector.timeline import Timeline

session = requests.Session()
secret_key = session.post("https://my.perekrestok.ru/api/v1/sessions/card/establish",
                          headers={"Content-type": "application/json"},
                          data=json.dumps({
                              "card_no":"<номер карты>",
                              "password":"<пароль>",
                          })).json()["data"]["totp_secret_key"]

timeline = Timeline()
offset = 0
while True:
    transactions = session.get("https://my.perekrestok.ru/api/v1/transactions?limit=5&offset=%d&type=I" % offset).json()["data"]["transaction_list"]
    if transactions:
        for transaction in transactions:
            if timeline.contains(transaction["id"]):
                sys.exit(0)

            timeline.store(transaction["id"], transaction, datetime=datetime.fromtimestamp(transaction["date"]))

        offset += len(transactions)
        time.sleep(5)
    else:
        sys.exit(0)
