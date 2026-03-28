import os
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.config import load_config


def run(config=None):
    if config is None:
        config = load_config()

    rtmp_addr = config["local"]["rtmp_addr"]
    pipe_path = os.path.join(ROOT_DIR, config["paths"]["pipe"])
    ff = config["ffmpeg"]

    cmd = (
        f'ffmpeg -stats -rw_timeout 5000000 -re -i {pipe_path}'
        f' -c:v copy -c:a aac -ac {ff["audio_channels"]}'
        f' -b:a {ff["audio_bitrate"]} -ar {ff["audio_sample_rate"]}'
        f' -af "volume={ff["volume"]}" -bsf:a aac_adtstoasc'
        f' -f flv "{rtmp_addr}"'
    )
    p = subprocess.Popen(cmd, shell=True)
    p.wait()


if __name__ == '__main__':
    run()
