#!/usr/bin/python3

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.bilibili_api import BilibiliAPI
from utils.config import load_config

config = load_config()
bili = BilibiliAPI(config)
bili.login_with_cookie()

while True:
    message = input("请输入消息：")
    bili.send_dm(message)
