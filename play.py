import subprocess
import time
import os
import json
from utils.blivex import Bilibili

bili = Bilibili()
bili.login_with_cookie('./data/cookie.json')

video_file = './data/videos.json'

while not bili.info["live_status"]:
    bili.start_live()
    time.sleep(5)
    bili.get_user_info()

rtmp_addr = bili.get_rtmp()

with open(video_file, 'r') as v_f:
    live_list = json.load(v_f)

file_list = []
cursor = int(live_list['cursor'])

for p in live_list['path']:
    f_li = [x for x in os.listdir(p) if (os.path.splitext(x)[1] == '.mp4')]
    f_li = sorted(f_li, key=lambda a: int(a[:-4]))
    file_list.extend( p+x for x in f_li)

pushList = file_list[cursor:] + file_list[:cursor] # 整合播放列表

startpoint = live_list['ss_time']

i = 0
retry = 0 # 断开重连计数器

while True:
    log_file = open('./data/live.log', 'a')
    e_start = time.time()
    log_content = (f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}]  {pushList[i]}")
    log_file.write(log_content + "\n")
    log_file.close()

    p = subprocess.Popen(f'ffmpeg -hide_banner -re -ss {startpoint} -fflags +genpts+igndts+ignidx+nobuffer+flush_packets -i {pushList[i]} -c copy -shortest -probesize 32 -max_interleave_delta 0 -use_wallclock_as_timestamps 1 -flush_packets 1 -flvflags +no_sequence_end+no_metadata+no_duration_filesize -f flv \"{rtmp_addr}\"', shell=True)
    p.wait()

    e_end = time.time()
    playtime = int(startpoint[3:5]) * 60 + int(startpoint[6:8]) + (e_end - e_start) # 计算单集视频的播放时长

    if retry == 5: # 超过重连次数，关闭直播间
        bili.stop_live()
        live_list['ss_time'] = startpoint
        with open(video_file, 'w') as w_f:
            json.dump(live_list, w_f, ensure_ascii=False)
        break

    if playtime < 2100: # 如果单集播放时长不足 35 分钟 2100 s = 35 min，则认为直播被断开，开始重启直播间
        bili.get_user_info()
        if not bili.info["live_status"]:
            bili.stop_live()
            time.sleep(300 * retry) # 每次断开，重连时间为 5 min 的倍数
            bili.start_live()
        retry = retry + 1
        startpoint = time.strftime('%H:%M:%S', time.gmtime(playtime)) # 计算上次播放位置
        continue

    i += 1
    startpoint = '00:00:00'
    retry = 0
    live_list['cursor'] = (cursor + i) % len(pushList)
    live_list['ss_time'] = startpoint
    with open(video_file, 'w') as w_f:
        json.dump(live_list, w_f, ensure_ascii=False)
    if i == len(pushList):
        i = 0
