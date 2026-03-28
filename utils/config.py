#!/usr/bin/python3

import os

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from dataclasses import dataclass, field

# 项目根目录（config.toml 所在目录）
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_config = None


def load_config(config_path=None):
    """加载 config.toml，返回字典。结果会缓存，多次调用返回同一对象。"""
    global _config
    if _config is not None:
        return _config

    if config_path is None:
        config_path = os.path.join(ROOT_DIR, "config.toml")

    with open(config_path, "rb") as f:
        _config = tomllib.load(f)
    return _config


@dataclass
class UserInfo:
    """用户信息类"""
    ban: bool = False
    coins: int = 0
    face: str = ""
    level: int = 0
    nickname: str = ""
    live_room: dict = field(default_factory=dict)
