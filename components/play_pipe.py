import subprocess
import time
import os
import json
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.config import load_config


def get_duration(file_name):
    """获取视频时长（秒）"""
    p = subprocess.Popen(
        ['ffprobe', '-i', file_name, '-show_entries', 'format=duration',
         '-v', 'quiet', '-of', 'csv=p=0'],
        stdout=subprocess.PIPE
    )
    output = p.stdout.readline().decode('utf8').strip()
    try:
        return int(float(output))
    except (ValueError, TypeError):
        return 0


def reshape_list(video_file):
    with open(video_file, 'r') as v_f:
        live_list = json.load(v_f)
    file_list = []
    cursor = int(live_list['cursor'])
    for p in live_list['path']:
        f_li = [x for x in os.listdir(p)
                if os.path.splitext(x)[1] in ('.mp4', '.ts', '.mkv')]
        f_li = sorted(f_li, key=lambda a: os.path.splitext(a)[0])
        file_list.extend(os.path.join(p, x) for x in f_li)
    pushList = file_list[cursor:] + file_list[:cursor]
    startpoint = live_list['ss_time']
    return (live_list, cursor, pushList, startpoint)


def run(config=None):
    if config is None:
        config = load_config()

    video_file = config["paths"]["videos_db"]
    push_pipe = os.path.join(ROOT_DIR, config["paths"]["pipe"])
    live_log = config["paths"]["live_log"]

    mtime = os.stat(video_file).st_mtime
    (live_list, cursor, pushList, startpoint) = reshape_list(video_file)

    i = 0

    while True:
        mtime = os.stat(video_file).st_mtime
        with open(live_log, 'a') as log_file:
            log_content = f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}]  {pushList[i]}"
            log_file.write(log_content + "\n")

        videotime = get_duration(pushList[i])
        e_start = time.time()

        cmd = [
            'ffmpeg', '-re', '-ss', startpoint,
            '-i', pushList[i],
            '-c', 'copy',
            '-f', 'mpegts', '-'
        ]
        with open(push_pipe, 'ab') as pipe:
            p = subprocess.Popen(cmd, stdout=pipe)
            p.wait()

        e_end = time.time()
        playtime = (int(startpoint[0:2]) * 3600 +
                    int(startpoint[3:5]) * 60 +
                    int(startpoint[6:8]) + (e_end - e_start))

        if mtime != os.stat(video_file).st_mtime:
            i = 0
            (live_list, cursor, pushList, startpoint) = reshape_list(video_file)
            continue

        if videotime - playtime > 180:
            startpoint = time.strftime('%H:%M:%S', time.gmtime(playtime))
            live_list['ss_time'] = startpoint
            with open(video_file, 'w') as w_f:
                json.dump(live_list, w_f, ensure_ascii=False)
            continue

        i += 1
        startpoint = '00:00:00'
        live_list['cursor'] = (cursor + i) % len(pushList)
        live_list['ss_time'] = startpoint
        with open(video_file, 'w') as w_f:
            json.dump(live_list, w_f, ensure_ascii=False)
        if i == len(pushList):
            i = 0


if __name__ == '__main__':
    run()
