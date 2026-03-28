#!/usr/bin/python3

import json
import os
import random
import time
from functools import reduce
from hashlib import md5
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import qrcode
import requests

from .config import load_config, UserInfo
from .exceptions import BilibiliError
from .logger import setup_logger

# 配置常量
APPKEY = "4409e2ce8ffd12b8"
APPSEC = "59b43e04ad6965f34319062b478f83dd"


class BilibiliAPI:
    """B站API封装类"""

    def __init__(self, config=None):
        self.config = config or load_config()
        self.session = requests.Session()
        self.user_info = UserInfo()
        log_file = self.config["paths"].get("login_log", "data/login.log")
        self.logger = setup_logger("bilibili_api", log_file)

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"]

        self._mixin_key_cache = None
        self._mixin_key_ts = 0

        self.api_headers = {
            'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9," +
                      "image/avif,image/webp,image/apng,*/*;q=0.8,application/" +
                      "signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "identity",
            'Connection': 'keep-alive',
            "Cache-Control": "max-age=0",
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': random.choice(user_agents)
        }

    def _get_sign(self, params: Dict[str, Any]) -> str:
        """生成 wbi 签名"""
        items = sorted(params.items())
        return md5(f"{urlencode(items)}{APPSEC}".encode("utf-8")).hexdigest()

    def _request(self, method: str, url: str, decode_level: int = 2, retry: int = 5,
                 timeout: int = 10, **kwargs) -> Optional[Any]:
        if method not in ["get", "post"]:
            return None

        for attempt in range(retry):
            try:
                response = getattr(self.session, method)(url, timeout=timeout, **kwargs)
                response.raise_for_status()

                if decode_level == 2:
                    return response.json()
                elif decode_level == 1:
                    return response.content
                else:
                    return response
            except requests.RequestException as e:
                self.logger.warning(f"请求{url}失败（尝试 {attempt + 1} / {retry}）:{e}")
                time.sleep(5 * (attempt + 1))
                if attempt + 1 == retry:
                    self.logger.error(f"最终请求失败：{url}")
        return None

    def get_uid(self) -> str:
        """从 cookies 中提取用户的 uid 信息"""
        return self.get_cookies().get("DedeUserID", "")

    def sign_params(self, params) -> str:
        mixin_key = self.get_mixin_key()
        filtered_params = {}
        for key, value in params.items():
            if value is not None and value != "":
                filtered_params[key] = str(value)
        sorted_params = sorted(filtered_params.items())
        query_string = "&".join([f"{key}={value}" for key, value in sorted_params])
        w_rid = md5((query_string + mixin_key).encode(encoding="utf-8")).hexdigest()
        return w_rid

    def get_tags(self, aid):
        url = f"https://api.bilibili.com/x/web-interface/view/detail/tag?" + \
              f"aid={aid}"
        response = self._request("get", url=url, headers=self.api_headers)
        return response

    def get_cid(self, aid):
        url = f"https://api.bilibili.com/x/player/pagelist?" + \
              f"aid={aid}"
        response = self._request("get", url=url, headers=self.api_headers)
        return response

    def get_vinfo(self, aid):
        url = f"https://api.bilibili.com/x/web-interface/view/detail?" + \
              f"aid={aid}"
        response = self._request("get", url=url, headers=self.api_headers)
        return response

    def get_vids(self, mid, pn) -> dict:
        """获取用户动态信息"""
        for _ in range(5):
            try:
                wts = int(time.time())
                params = {"mid": mid, "pn": pn, "wts": wts}
                w_rid = self.sign_params(params)
                url = f"https://api.bilibili.com/x/space/wbi/arc/search?" + \
                      f"mid={mid}&pn={pn}&w_rid={w_rid}&wts={wts}"
                response = self._request("get", url, headers=self.api_headers)
                if response and response.get("code") == 0:
                    data = response["data"]
                    return data
                else:
                    continue
            except Exception as e:
                self.logger.error(f"获取用户(mid={mid})视频信息失败：{e}")
        return {}

    def get_user_info(self) -> bool:
        """用于获取用户信息，并返回当前的登录状态。检测到 cookie 失效时自动重新加载。"""
        try:
            wts = int(time.time())
            params = {"mid": self.get_uid(), "wts": wts}
            w_rid = self.sign_params(params)
            url = "https://api.bilibili.com/x/space/wbi/acc/info?" + \
                  f"mid={self.get_uid()}&w_rid={w_rid}&wts={wts}"
            response = self._request("get", url, headers=self.api_headers)

            if response and response.get("code") == -101:
                self.logger.warning("Cookie 已失效，尝试重新加载")
                cookie_file = self.config["bilibili"]["cookie_file"]
                return self.login_with_cookie(cookie_file)

            if response and response.get("code") == 0:
                data = response["data"]
                self.user_info.ban = bool(data["silence"])
                self.user_info.coins = data["coins"]
                self.user_info.face = data["face"]
                self.user_info.level = data["level"]
                self.user_info.nickname = data["name"]
                self.user_info.live_room = data["live_room"]

                status = "状态正常" if not self.user_info.ban else "被封禁"
                live_status = "正在直播" if self.user_info.live_room.get("liveStatus")\
                              else "停播状态"
                self.logger.info(
                    f"{self.user_info.nickname}(UID={self.get_uid()})，"
                    f"Lv.{self.user_info.level}，拥有 {self.user_info.coins} 枚硬币，"
                    f"账号{status}"
                )
                return True
        except Exception as e:
            self.logger.error(f"获取用户信息失败：{e}")
        return False

    def get_cookies(self) -> Dict[str, str]:
        """获取 cookies """
        return self.session.cookies.get_dict(domain=".bilibili.com")

    def get_mixin_key(self) -> str:
        """获取混合密钥，缓存 30 分钟"""
        # 缓存有效期内直接返回
        if self._mixin_key_cache and (time.time() - self._mixin_key_ts) < 1800:
            return self._mixin_key_cache

        url = "https://api.bilibili.com/x/web-interface/nav"
        response = self._request("get", url, headers=self.api_headers)

        if not response or response.get("code") != 0:
            # 如果请求失败但有缓存，返回旧缓存
            if self._mixin_key_cache:
                self.logger.warning("刷新混合密钥失败，使用缓存")
                return self._mixin_key_cache
            raise BilibiliError("获取混合密钥失败")

        # wbi 鉴权
        wbi_img = response["data"]["wbi_img"]
        img_url = wbi_img.get("img_url")
        sub_url = wbi_img.get("sub_url")

        img_value = img_url.split("/")[-1].split(".")[0]
        sub_value = sub_url.split("/")[-1].split(".")[0]
        ae = img_value + sub_value

        oe = [46, 47, 18,  2, 53,  8, 23, 32, 15, 50, 10, 31, 58,  3, 45, 35, 27,
              43,  5, 49, 33,  9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48,
              7,  16, 24, 55, 40, 61, 26, 17,  0,  1, 60, 51, 30,  4, 22, 25, 54,
              21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]

        le = reduce(lambda s, i: s + ae[i], oe, "")
        self._mixin_key_cache = le[:32]
        self._mixin_key_ts = time.time()
        return self._mixin_key_cache

    def login_with_cookie(self, cookie_file: Optional[str] = None) -> bool:
        """使用 cookies 进行登录"""
        cookie_file = cookie_file or self.config["bilibili"]["cookie_file"]

        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                temp_cookie = json.load(f)
            for key, value in temp_cookie.items():
                self.session.cookies.set(key, value, domain=".bilibili.com")

            if self.get_user_info():
                self.logger.info("使用 cookie 登录成功")
                return True
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"使用 cookie 登录失败：{e}")
        return False

    def login_with_qrcode(self, cookie_file: Optional[str] = None) -> bool:
        """使用二维码登录"""
        cookie_file = cookie_file or self.config["bilibili"]["cookie_file"]
        params = {
            "appkey": APPKEY,
            "local_id": 0,
            "ts": int(time.time())
        }
        params["sign"] = self._get_sign(params)

        url = "http://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
        response = self._request("post", url, data=params, headers=self.api_headers)

        if not response or response.get("code") != 0:
            self.logger.error("获取二维码失败")
            return False

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=1,
            border=1
        )
        qr.add_data(response["data"]["url"])
        matrix = qr.get_matrix()
        for i in range(0, len(matrix), 2):
            line = ""
            for j in range(len(matrix[0])):
                top = matrix[i][j] if i < len(matrix) else False
                bottom = matrix[i+1][j] if i+1 < len(matrix) else False

                if top and bottom:
                    line += "\u2588"
                elif top:
                    line += "\u2580"
                elif bottom:
                    line += "\u2584"
                else:
                    line += " "
            print(line)
        self.logger.info("请扫描二维码登录")

        # 轮询登录状态
        params = {
            "appkey": APPKEY,
            "local_id": 0,
            "ts": int(time.time()),
            "auth_code": response["data"]["auth_code"]
        }
        params["sign"] = self._get_sign(params)

        poll_url = "http://passport.bilibili.com/x/passport-tv-login/qrcode/poll"

        while True:
            poll_response = self._request("post", poll_url, data=params,
                                          headers=self.api_headers)
            if poll_response and poll_response.get("code") == 0:
                break
            time.sleep(3)

        # 保存 cookie
        temp_cookie = {}
        for item in poll_response["data"]["cookie_info"]["cookies"]:
            temp_cookie[item["name"]] = item["value"]

        # 获取 buvid3/4
        buvid_url = "https://api.bilibili.com/x/frontend/finger/spi"
        response = self._request("get", buvid_url, headers=self.api_headers)
        if not response or response.get("code") != 0:
            self.logger.error("获取 buvid3/4 失败")
        else:
            temp_cookie["buvid3"] = response["data"]["b_3"]
            temp_cookie["buvid4"] = response["data"]["b_4"]

        os.makedirs(os.path.dirname(cookie_file), exist_ok=True)
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(temp_cookie, f, ensure_ascii=False, indent=2)

        for key, value in temp_cookie.items():
            self.session.cookies.set(key, value, domain=".bilibili.com")

        if self.get_user_info():
            self.logger.info("使用二维码登录成功")
            return True

        return False

    def start_live(self):
        url = "https://api.live.bilibili.com/xlive/app-blink/v1/streaming/"
        wts = int(time.time())
        payload = {
            'room_id': self.user_info.live_room.get('roomid'),
            'platform': 'pc',
            'area_v2': self.config["bilibili"]["area_id"],
            'backup_stream': "0",
            'csrf_token': self.session.cookies['bili_jct'],
            'csrf': self.session.cookies['bili_jct'],
            'wts': wts
        }
        w_rid = self.sign_params(payload)
        payload.setdefault("w_rid", w_rid)
        tail_url = "&".join([str(x[0])+"="+str(x[1]) for x in payload.items()])
        url = url + "WebLiveCenterStartLive?" + tail_url
        response = self._request("post", url, data=payload, headers=self.api_headers)
        self.rtmp_addr = self.get_rtmp()
        if not self.rtmp_addr:
            self.logger.info("开启直播间失败")
            return False
        self.logger.info("开启直播间成功，串流地址为：" + self.rtmp_addr)
        return True

    def switch_room(self, roomid):
        url = "https://api.live.bilibili.com/room/v1/Room/update"
        payload = {
            'room_id': self.user_info.live_room.get('roomid'),
            'area_id': roomid,
            'csrf_token': self.session.cookies['bili_jct'],
            'csrf': self.session.cookies['bili_jct'],
        }
        response = self._request("post", url, data=payload, headers=self.api_headers)
        return response

    def get_rtmp(self):
        url = "https://api.live.bilibili.com/xlive/app-blink/v1/live/FetchWebUpStreamAddr"
        payload = {
            'platform': 'pc',
            'backup_stream': '0',
            'csrf_token': self.session.cookies['bili_jct'],
            'csrf': self.session.cookies['bili_jct'],
        }
        response = self._request("post", url, data=payload, headers=self.api_headers)
        try:
            addr_info = response["data"]["addr"]
            self.rtmp_addr = addr_info["addr"] + addr_info["code"]
            return self.rtmp_addr
        except (TypeError, KeyError) as e:
            self.logger.error(f"获取 RTMP 地址失败：{e}")
            return None

    def stop_live(self):
        url = "https://api.live.bilibili.com/room/v1/Room/stopLive"
        payload = {
            'room_id': self.user_info.live_room.get('roomid'),
            'platform': 'pc',
            'csrf_token': self.session.cookies['bili_jct'],
            'csrf': self.session.cookies['bili_jct'],
        }
        self._request("post", url, data=payload, headers=self.api_headers)
        self.logger.info("正在关闭直播间")
        return True

    def send_dm(self, message):
        url = "https://api.live.bilibili.com/msg/send"
        dm_config = self.config["bilibili"]["danmaku"]
        payload = {
            'color': str(dm_config["color"]),
            'fontsize': str(dm_config["fontsize"]),
            'mode': str(dm_config["mode"]),
            'msg': message,
            'rnd': str(int(time.time())),
            'roomid': self.user_info.live_room.get('roomid'),
            'bubble': '0',
            'csrf_token': self.session.cookies['bili_jct'],
            'csrf': self.session.cookies['bili_jct']
        }
        response = self._request("post", url, data=payload, headers=self.api_headers)
        return response
