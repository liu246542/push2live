# -*- coding: utf-8 -*-
import asyncio
import time
import json
import os
import sys
import aiohttp

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import blivedm
from utils.bilibili_api import BilibiliAPI
from utils.config import load_config


_config = None
_bili = None


async def load_custom_session(cookie_file):
    with open(cookie_file, "r") as f:
        custom_session = json.load(f)
    session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
    for k, v in custom_session.items():
        session.cookie_jar.update_cookies({k: v})
    return session


async def run_client(config):
    room_id = str(config["bilibili"]["room_id"])
    cookie_file = config["bilibili"]["cookie_file"]
    with open(cookie_file, "r") as f:
        cookie_data = json.load(f)
    uid = int(cookie_data.get("DedeUserID", 0))
    custom_session = await load_custom_session(cookie_file)
    client = blivedm.BLiveClient(room_id, uid=uid, session=custom_session, ssl=True)
    handler = MyHandler(config)
    client.add_handler(handler)

    client.start()
    await client.join()


class MyHandler(blivedm.BaseHandler):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.dm_log = config["paths"]["dm_log"]
        self.qz_flag = config["paths"]["qz_flag"]

    async def _on_danmaku(self, client: blivedm.BLiveClient, message: blivedm.DanmakuMessage):
        temp_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}] #{message.uname}: {message.msg}"
        with open(self.dm_log, 'a') as f:
            f.write(temp_message + "\n")

    async def _on_warning(self, client: blivedm.BLiveClient, message: blivedm.WARNING):
        global _bili
        temp_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}] [警告]{message.msg}"
        with open(self.dm_log, 'a') as f:
            f.write(temp_message + "\n")
        with open(self.qz_flag, 'w') as f:
            f.write('1')
        _bili.stop_live()
        _bili.send_dm("[Bot]版权警告")

    async def _on_cutoff(self, client: blivedm.BLiveClient, message: blivedm.CutOff):
        global _bili
        temp_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}] [警告]{message.msg}"
        with open(self.dm_log, 'a') as f:
            f.write(temp_message + "\n")
        with open(self.qz_flag, 'w') as f:
            f.write('1')
        _bili.stop_live()

    async def _on_gift(self, client: blivedm.BLiveClient, message: blivedm.GiftMessage):
        temp_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}] #{message.uname} 赠送{message.gift_name}x{message.num} （{message.coin_type}瓜子x{message.total_coin}）"
        with open(self.dm_log, 'a') as f:
            f.write(temp_message + "\n")

    async def _on_watched(self, client: blivedm.BLiveClient, message: blivedm.WATCHED_CHANGE):
        pass

    async def _on_likeinfo(self, client: blivedm.BLiveClient, message: blivedm.LIKE_INFO_V3_CLICK):
        temp_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}] {message.msg}"
        with open(self.dm_log, 'a') as f:
            f.write(temp_message + "\n")

    async def _on_likeupdate(self, client: blivedm.BLiveClient, message: blivedm.LIKE_INFO_V3_UPDATE):
        pass

    async def _on_buy_guard(self, client: blivedm.BLiveClient, message: blivedm.GuardBuyMessage):
        print(f'[{client.room_id}] {message.username} 购买{message.gift_name}')

    async def _on_super_chat(self, client: blivedm.BLiveClient, message: blivedm.SuperChatMessage):
        print(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')


def run(config=None):
    global _config, _bili
    if config is None:
        config = load_config()
    _config = config

    _bili = BilibiliAPI(config)
    _bili.login_with_cookie()

    asyncio.get_event_loop().run_until_complete(run_client(config))


if __name__ == '__main__':
    run()
