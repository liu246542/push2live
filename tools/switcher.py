#!/usr/bin/python3

import time
import os
import sys
import random

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.bilibili_api import BilibiliAPI
from utils.config import load_config

config = load_config()
bili = BilibiliAPI(config)
bili.login_with_cookie()

sw_config = config["switcher"]
room_list = [str(x) for x in sw_config["area_ids"]]
name_list = sw_config["area_names"]
interval = sw_config.get("interval", 60)

while True:
    ct = random.choice(list(range(len(name_list))))
    bili.switch_room(room_list[ct])
    print("切换为：" + name_list[ct])
    time.sleep(interval)
