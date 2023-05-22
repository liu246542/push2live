#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-

import requests
import time
import qrcode
from hashlib import md5
from urllib.parse import urlencode
import json

APPKEY = "4409e2ce8ffd12b8"
APPSEC = "59b43e04ad6965f34319062b478f83dd"

def get_sign(params):
    items = sorted(params.items())
    return md5(f"{urlencode(items)}{APPSEC}".encode('utf-8')).hexdigest()

class Bilibili:
    def __init__(self):
        self._session = requests.Session()
        self.get_cookies = lambda: self._session.cookies.get_dict(domain=".bilibili.com")
        self.get_uid = lambda: self.get_cookies().get("DedeUserID", "")
        self.info = {
            'ban': False,
            'coins': 0,
            'face': "",
            'level': 0,
            'nickname': "",
            'room_id': "",
            'live_status': False
        }
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "referrer": "https://link.bilibili.com/p/center/index",
            "referrerPolicy": "no-referrer-when-downgrade"
        }

    @staticmethod
    def _log(message):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}] {message}")

    def _requests(self, method, url, decode_level=2, retry=5, timeout=10, **kwargs):
        if method in ["get", "post"]:
            for _ in range(retry + 1):
                try:
                    response = getattr(self._session, method)(url, timeout=timeout, **kwargs)
                    return response.json() if decode_level == 2 else response.content if decode_level == 1 else response
                except:
                    pass
        return None

    # 使用 cookie 登陆
    def login_with_cookie(self, fcookie):
        import json
        with open(fcookie) as f:
            tempCookie = json.load(f)
        for k in tempCookie.keys():
            self._session.cookies.set(k, tempCookie[k], domain=".bilibili.com")            
        if self.get_user_info():
            self._log("登录成功")
            return True
        return False

    def login_with_qrcode(self):
        params = {
            "appkey": APPKEY,
            "local_id": 0,
            "ts": int(time.time())
        }
        params["sign"] = get_sign(params)
        url = f"http://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
        response = self._requests("post", url, data=params)
        print(response)
        qr = qrcode.QRCode()
        qr.add_data(response["data"]["url"])
        img = qr.make_image()
        img.show()

        params = {
            "appkey": APPKEY,
            "local_id": 0,
            "ts": int(time.time())
        }
        params["auth_code"] = response["data"]["auth_code"]
        params["sign"] = get_sign(params)
        url = f"http://passport.bilibili.com/x/passport-tv-login/qrcode/poll"
        while True:
            response = self._requests("post", url, data=params)
            print(response)
            if response["code"] == 0:
                break
            time.sleep(5)
        tempCookie = {}
        for item in response["data"]["cookie_info"]["cookies"]:
            tempCookie.setdefault(item["name"], item["value"])
        with open("../data/cookie.json", "w") as w_f:
            json.dump(tempCookie, w_f)
        for k in tempCookie.keys():
            self._session.cookies.set(k, tempCookie[k], domain=".bilibili.com")            
        if self.get_user_info():
            self._log("登录成功")
            return True
        return False
  
    # 获取用户信息
    def get_user_info(self):
        url = f"https://api.bilibili.com/x/space/wbi/acc/info?mid={self.get_uid()}&jsonp=jsonp"
        headers = {
            'authority': "api.bilibili.com",
            'accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            'user-agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36",
            'Host': "api.bilibili.com",
            'Referer': f"https://space.bilibili.com/{self.get_uid()}/",
        }
        response = self._requests("get", url, headers=headers)
        if response and response.get("code") == 0:
            self.info['ban'] = bool(response['data']['silence'])
            self.info['coins'] = response['data']['coins']
            self.info['face'] = response['data']['face']
            self.info['level'] = response['data']['level']
            self.info['nickname'] = response['data']['name']
            self.info['room_id'] = response['data']['live_room']['roomid']
            self.info['live_status'] = bool(response['data']['live_room']['liveStatus'])
            # self.room_info = self._requests("get", "https://api.live.bilibili.com/xlive/app-blink/v1/room/GetInfo?platform=pc").get("data")
            self._log(f"{self.info['nickname']}(UID={self.get_uid()}), Lv.{self.info['level']}, 拥有{self.info['coins']}枚硬币, 账号{'状态正常' if not self.info['ban'] else '被封禁'}, 直播间ID={self.info['room_id']}, {'正在直播' if self.info['live_status'] else '停播状态'}")
            return True
        else:
            self._log("用户信息获取失败")
            return False

    def start_live(self):                
        url = "https://api.live.bilibili.com/room/v1/Room/startLive"
        payload = {
            'room_id': self.info['room_id'],
            'platform': 'pc',
            'area_v2': 33, # 此处可以手动设置，如，33: 影音馆，376: 学习-人文社科
            'csrf_token': self._session.cookies['bili_jct'],
            'csrf': self._session.cookies['bili_jct'],
        }
        headers = {
            'authority': "api.live.bilibili.com",
            'accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            'user-agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
        }
        response = self._requests("post", url, data=payload, headers=self.headers).get("data")
        self.rtmp_addr = response.get("rtmp").get("addr") + response.get("rtmp").get("code")
        if not self.rtmp_addr:
            self._log("开启直播间失败")
            return False
        self._log("开启直播间成功，串流地址为：" + self.rtmp_addr)
        return True

    def switch_room(self, roomid):
        url = "https://api.live.bilibili.com/room/v1/Room/update"
        payload = {
            'room_id': self.info['room_id'],
            'area_id': roomid, # 此处可以手动设置，如，33: 影音馆，376: 学习-人文社科
            'csrf_token': self._session.cookies['bili_jct'],
            'csrf': self._session.cookies['bili_jct'],
        }
        response = self._requests("post", url, data=payload, headers=self.headers)

    def get_rtmp(self):
        url = "https://api.live.bilibili.com/xlive/app-blink/v1/live/FetchWebUpStreamAddr"
        payload = {
            'platform': 'pc',
            'csrf_token': self._session.cookies['bili_jct'],
            'csrf': self._session.cookies['bili_jct'],
        }

        response = self._requests("post", url, data=payload, headers=self.headers).get("data").get("addr")
        self.rtmp_addr = response.get("addr") + response.get("code")
        return self.rtmp_addr

    def stop_live(self):
        url = "https://api.live.bilibili.com/room/v1/Room/stopLive"
        payload = {
            'room_id': self.info['room_id'],
            'platform': 'pc',
            'csrf_token': self._session.cookies['bili_jct'],
            'csrf': self._session.cookies['bili_jct'],
        }
        response = self._requests("post", url, data=payload, headers=self.headers)
        self._log("正在关闭直播间")
        return True

    def send_dm(self, message):
        url = "https://api.live.bilibili.com/msg/send"
        payload = {
            'color': '16777215',
            'fontsize': '25',
            'mode': '1',
            'msg': message,
            'rnd': str(int(time.time())),
            'roomid': self.info['room_id'],
            'bubble': '0',
            'csrf_token': self._session.cookies['bili_jct'],
            'csrf': self._session.cookies['bili_jct']
        }
        response = self._requests("post", url, data=payload, headers=self.headers)
        return response
