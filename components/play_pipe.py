import signal
import subprocess
import time
import os
import json
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

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
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                proc.terminate()
            proc.wait(timeout=5)
            return True
        time.sleep(poll_interval)
    return False


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
    qz_flag_path = config["paths"]["qz_flag"]

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

        pipe_command = config.get("ffmpeg", {}).get("pipe_command", "")
        if pipe_command:
            cmd = f'{pipe_command} {startpoint} "{pushList[i]}" {push_pipe}'
            p = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
        else:
            cmd = [
                'ffmpeg', '-re', '-ss', startpoint,
                '-i', pushList[i],
                '-c', 'copy',
                '-f', 'mpegts', '-'
            ]
            pipe_fd = open(push_pipe, 'ab')
            p = subprocess.Popen(cmd, stdout=pipe_fd, preexec_fn=os.setsid)

        cut = _wait_or_kill(p, qz_flag_path)
        if not pipe_command:
            pipe_fd.close()
        if cut:
            print("[play_pipe] 收到切断信号，已终止 ffmpeg")
            # 等待 qz_flag 恢复为 0 再继续
            while _check_qz_flag(qz_flag_path):
                time.sleep(5)
            continue

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
