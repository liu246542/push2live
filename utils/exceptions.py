#!/usr/bin/python3


class BilibiliError(Exception):
    """B站相关异常"""
    pass


class LoginError(BilibiliError):
    """登录异常"""
    pass
