import os
import subprocess
import time
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.bilibili_api import BilibiliAPI
from utils.config import load_config


def run(config=None):
    if config is None:
        config = load_config()

    qz_flag_path = config["paths"]["qz_flag"]
    pipe_path = os.path.join(ROOT_DIR, config["paths"]["pipe"])
    ff = config["ffmpeg"]

    with open(qz_flag_path, 'r') as f:
        qz_flag = f.read()

    print(qz_flag)

    if qz_flag == "1":
        os._exit(0)

    bili = BilibiliAPI(config)
    bili.login_with_cookie()

    while not bili.user_info.live_room.get("liveStatus"):
        bili.start_live()
        time.sleep(5)
        bili.get_user_info()

    rtmp_addr = bili.get_rtmp()

    while True:
        with open(qz_flag_path, "r") as f:
            qz_flag = f.read()

        if qz_flag == "1":
            break

        try:
            bili.get_user_info()
            if not bili.user_info.live_room.get("liveStatus"):
                bili.start_live()
                time.sleep(5)
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
        p = subprocess.Popen(cmd, shell=True)
        p.wait()
        time.sleep(5)
        bili.stop_live()


if __name__ == '__main__':
    run()
