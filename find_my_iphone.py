# -*- coding: utf-8 -*-
# crontab(minute="*/10")
# title = 'Обновление Find My iPhone'
import requests
from requests.auth import HTTPBasicAuth

from themylog.collector.time_series import TimeSeries

USERNAME = "<e-mail>"
PASSWORD = "<password>"

auth = HTTPBasicAuth(USERNAME, PASSWORD)
headers = {
    "Accept-Language":          "en-us",
    "Connection":               "keep-alive",
    "Content-Type":             "application/json; charset=utf-8",
    "User-agent":               "Find iPhone/1.3 MeKit (iPad: iPhone OS/4.2.1)",
    "X-Apple-Authscheme":       "UserIdGuest",
    "X-Apple-Find-Api-Ver":     "2.0",
    "X-Apple-Realm-Support":    "1.0",
    "X-Client-Name":            "iPad",
    "X-Client-UUID":            "0cf3dc501ff812adb0b202baed4f37274b210853",
}

stage1 = requests.post("https://fmipmobile.icloud.com/fmipservice/device/%s/initClient" % USERNAME, auth=auth, data={}, headers=headers)
stage2 = requests.post("https://%s/fmipservice/device/%s/initClient" % (stage1.headers["X-Apple-MMe-Host"], USERNAME), auth=auth, data={}, headers=headers)

ts = TimeSeries()
ts.data(stage2.json())
