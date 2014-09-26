# -*- coding: utf-8 -*-
# crontab(minute="*/30")
# title = 'Обновление баланса ВТБ24'
from __future__ import unicode_literals

import datetime
import dateutil.parser
import email
import html2text
import imaplib
import re

from themylog.collector.timeline import Timeline

mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login("<login>", "<password>")
mail.list()
mail.select("inbox")

timeline = Timeline()
for uid in reversed(mail.uid("search", None, "(FROM \"notify@vtb24.ru\")")[1][0].split()):
    if timeline.contains(uid):
        break

    result, data = mail.uid("fetch", uid, "(RFC822)")
    raw_email = data[0][1]

    email_message = email.message_from_string(raw_email)
    maintype = email_message.get_content_maintype()
    if maintype == "multipart":
        text = ""
        for part in email_message.get_payload():
            if part.get_content_maintype() == "text":
                text += part.get_payload(decode=True)
    elif maintype == "text":
        text = email_message.get_payload(decode=True)
    text = text.decode("utf-8")
    
    h = html2text.HTML2Text()
    h.body_width = 0
    text = h.handle(text)

    datetime_match = re.search("[0-9.]+ в [0-9:]+", text)
    if datetime_match is None:
        continue

    balance_match = re.search("Доступно.+?([0-9.]+) RUR", text)
    if balance_match is None:
        continue

    args = {}
    args["text"] = text

    datetime_ = dateutil.parser.parse(datetime_match.group(0).replace("в", ""), dayfirst=True) - datetime.timedelta(hours=4) + datetime.timedelta(hours=7)

    charge_match = re.search("(увеличен баланс|произведено зачисление|произведено внесение|произведена транзакция по зачислению|произведена транзакция по внесению).+?([0-9.]+) (RUR|USD)", text)
    write_off_match = re.search("(уменьшен баланс|произведено снятие|произведена оплата|произведена транзакция по оплате|произведена транзакция по снятию).+?([0-9.]+) (RUR|USD)", text)
    if charge_match:
        args["charge"] = float(charge_match.group(2))
        args["charge_currency"] = charge_match.group(3)
    elif write_off_match:
        args["write_off"] = float(write_off_match.group(2))
        args["write_off_currency"] = write_off_match.group(3)
    else:
        raise Exception("Neither charge nor write-off match found in '%s'" % text)

    details_match = re.search("Детали платежа: (место - )?(.+)", text)
    if details_match:
        args["details"] = re.sub(", код авторизации.+", "", details_match.group(2))

    args["balance"] = float(balance_match.group(1))

    timeline.store(uid, args, datetime=datetime_)
