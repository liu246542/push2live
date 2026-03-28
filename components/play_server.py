import os
import signal
import subprocess
import time
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.bilibili_api import BilibiliAPI
from utils.config import load_config


def _check_qz_flag(path):
    """读取 qz_flag，返回是否需要停止"""
    try:
        with open(path, "r") as f:
            return f.read().strip() == "1"
    except FileNotFoundError:
        return False


def _wait_or_kill(proc, qz_flag_path, poll_interval=2):
    """轮询等待子进程结束，期间检查 qz_flag，发现切断时杀掉进程"""
    while proc.poll() is None:
        if _check_qz_flag(qz_flag_path):
            # 先发 SIGTERM 让 ffmpeg 优雅退出
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                proc.terminate()
            proc.wait(timeout=5)
            return True  # 被切断
        time.sleep(poll_interval)
    return False  # 正常结束


def run(config=None):
    if config is None:
        config = load_config()

    qz_flag_path = config["paths"]["qz_flag"]
    pipe_path = os.path.join(ROOT_DIR, config["paths"]["pipe"])
    ff = config["ffmpeg"]

    if _check_qz_flag(qz_flag_path):
        os._exit(0)

    bili = BilibiliAPI(config)
    bili.login_with_cookie()

    while not bili.user_info.live_room.get("liveStatus"):
        bili.start_live()
        time.sleep(5)
        bili.get_user_info()

    rtmp_addr = bili.get_rtmp()

    while True:
        if _check_qz_flag(qz_flag_path):
            break

        try:
            bili.get_user_info()
            if not bili.user_info.live_room.get("liveStatus"):
                bili.start_live()
                time.sleep(5)
            # 每轮刷新 RTMP 地址（断线重连后地址可能变化）
            new_addr = bili.get_rtmp()
            if new_addr:
                rtmp_addr = new_addr
        except Exception as e:
            print(e)
            time.sleep(30)
            continue

        cmd = (
            f'ffmpeg -re -i {pipe_path} -c:v copy -c:a aac'
            f' -ac {ff["audio_channels"]} -b:a {ff["audio_bitrate"]}'
            f' -ar {ff["audio_sample_rate"]} -af "volume={ff["volume"]}"'
            f' -async 1 -bsf:v h264_mp4toannexb -bsf:a aac_adtstoasc'
            f' -shortest -flags low_delay -use_wallclock_as_timestamps 1'
            f' -vsync drop -bufsize {ff["buffer_size"]} -maxrate {ff["max_bitrate"]}'
            f' -f flv -fflags +genpts'
            f' -flvflags no_sequence_end+no_metadata+no_duration_filesize'
            f' -reset_timestamps 1 -rw_timeout 0 -rtmp_live live'
            f' -rtmp_buffer {ff["rtmp_buffer"]} -rtsp_transport tcp'
            f' "{rtmp_addr}"'
        )
        p = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
        cut = _wait_or_kill(p, qz_flag_path)
        if cut:
            print("[play_server] 收到切断信号，已终止 ffmpeg")
            break
        time.sleep(5)
        bili.stop_live()


if __name__ == '__main__':
    run()
