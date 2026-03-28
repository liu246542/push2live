#!/usr/bin/python3

import argparse
import multiprocessing
import os
import signal
import sys
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from utils.config import load_config


def run_component(name, target_func, config):
    """运行组件的包装函数，用于子进程"""
    try:
        print(f"[{name}] 启动中...")
        target_func(config)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[{name}] 异常退出: {e}")


def start_process(name, target_func, config):
    """启动一个子进程"""
    p = multiprocessing.Process(
        target=run_component,
        args=(name, target_func, config),
        name=name,
        daemon=True
    )
    p.start()
    return p


def main():
    parser = argparse.ArgumentParser(description="push2live - B站直播推流系统")
    parser.add_argument("--local", action="store_true",
                        help="本地模式：仅启动 pipe + server_local")
    parser.add_argument("--no-tg", action="store_true",
                        help="不启动 Telegram 机器人")
    parser.add_argument("--no-dm", action="store_true",
                        help="不启动弹幕监听")
    args = parser.parse_args()

    config = load_config()

    # 重置 qz_flag
    qz_flag_path = config["paths"]["qz_flag"]
    with open(qz_flag_path, "w") as f:
        f.write("0")

    from components.play_pipe import run as pipe_run

    processes = {}

    # play_pipe 始终启动
    processes["pipe"] = start_process("pipe", pipe_run, config)

    if args.local:
        from components.play_server_local import run as server_local_run
        processes["server"] = start_process("server", server_local_run, config)
    else:
        from components.play_server import run as server_run
        processes["server"] = start_process("server", server_run, config)

        if not args.no_dm:
            from components.dmbot import run as dmbot_run
            processes["dmbot"] = start_process("dmbot", dmbot_run, config)

        if not args.no_tg:
            from components.tg_bot import run as tgbot_run
            processes["tgbot"] = start_process("tgbot", tgbot_run, config)

    component_names = ", ".join(processes.keys())
    print(f"[main] 已启动组件: {component_names}")
    print(f"[main] 按 Ctrl+C 停止所有组件")

    # 监控子进程，崩溃自动重启
    try:
        while True:
            for name, proc in list(processes.items()):
                if not proc.is_alive():
                    print(f"[main] 组件 {name} 已退出 (exitcode={proc.exitcode})，正在重启...")
                    if name == "pipe":
                        from components.play_pipe import run as func
                    elif name == "server" and args.local:
                        from components.play_server_local import run as func
                    elif name == "server":
                        from components.play_server import run as func
                    elif name == "dmbot":
                        from components.dmbot import run as func
                    elif name == "tgbot":
                        from components.tg_bot import run as func
                    else:
                        continue
                    processes[name] = start_process(name, func, config)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n[main] 正在停止所有组件...")
        for name, proc in processes.items():
            if proc.is_alive():
                proc.terminate()
        for name, proc in processes.items():
            proc.join(timeout=10)
            if proc.is_alive():
                proc.kill()
        # 关闭远程直播间
        if not args.local:
            try:
                from utils.bilibili_api import BilibiliAPI
                bili = BilibiliAPI(config)
                bili.login_with_cookie()
                bili.stop_live()
                print("[main] 已关闭远程直播间")
            except Exception as e:
                print(f"[main] 关闭直播间失败: {e}")
        print("[main] 所有组件已停止")


if __name__ == "__main__":
    main()
