import subprocess
import time
import os
import json
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.config import load_config


def get_time(file_name):
    p = subprocess.Popen(
        f'ffprobe -i {file_name} -show_entries format=duration -v quiet -of csv="p=0" -sexagesimal',
        shell=True, stdout=subprocess.PIPE
    )
    e_time = p.stdout.readline().decode('utf8')
    return (
        "0" + e_time[0:1] + "\\\\:" + e_time[2:4] + "\\\\" + e_time[4:7],
        int(e_time[0:1]) * 3600 + int(e_time[2:4]) * 60 + int(e_time[5:7])
    )


def reshape_list(video_file):
    with open(video_file, 'r') as v_f:
        live_list = json.load(v_f)
    file_list = []
    cursor = int(live_list['cursor'])
    for p in live_list['path']:
        f_li = [x for x in os.listdir(p + "videos/")
                if os.path.splitext(x)[1] in ('.mp4', '.ts', '.mkv')]
        f_li = sorted(f_li, key=lambda a: os.path.splitext(a)[0])
        file_list.extend(p + "videos/" + x for x in f_li)
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
    cutid = 1

    while True:
        mtime = os.stat(video_file).st_mtime
        log_file = open(live_log, 'a')
        log_content = f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}]  {pushList[i]}"
        log_file.write(log_content + "\n")
        log_file.close()
        (videotime_s, videotime) = get_time(pushList[i])

        e_start = time.time()

        (pname, fname) = os.path.split(pushList[i])
        fname = os.path.splitext(fname)[0]

        p = subprocess.Popen(
            f'cd {pname}/.. && bash play2.sh {startpoint} {fname} {push_pipe} {videotime_s}',
            shell=True
        )
        p.wait()

        e_end = time.time()
        playtime = (int(startpoint[0:2]) * 3600 +
                    int(startpoint[3:5]) * 60 +
                    int(startpoint[6:8]) + (e_end - e_start))

        if mtime != os.stat(video_file).st_mtime:
            i = 0
            cutid = 1
            (live_list, cursor, pushList, startpoint) = reshape_list(video_file)
            continue

        if videotime - playtime > 180:
            cutid += 1
            startpoint = time.strftime('%H:%M:%S', time.gmtime(playtime))
            live_list['ss_time'] = startpoint
            with open(video_file, 'w') as w_f:
                json.dump(live_list, w_f, ensure_ascii=False)
            continue

        i += 1
        cutid = 1
        startpoint = '00:00:00'
        live_list['cursor'] = (cursor + i) % len(pushList)
        live_list['ss_time'] = startpoint
        with open(video_file, 'w') as w_f:
            json.dump(live_list, w_f, ensure_ascii=False)
        if i == len(pushList):
            i = 0


if __name__ == '__main__':
    run()
