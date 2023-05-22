# 推送本地视频到b站直播间

## 使用说明

本项目依赖 `requests` 和 `qrcode`，可以直接使用 `pip` 安装：

```
pip install -r requirements.txt
```

使用二维码登录并生成 `cookie.json`：

```
from utils.blivex import Bilibili
bili = Bilibili()
bili.login_with_qrcode("./data/cookie.json") # 可以自定义 `cookie.json` 的存储位置
```

生成 `cookie.json` 之后便可以直接用 `cookie` 登录：

```
bili.login_with_cookie("./data/cookie.json")
```

推送本地视频到直播间示例：

```
bili.start_live() # 开启直播间
rtmp_addr = bili.get_rtmp() # 获取直播 rtmp 地址
ffmpeg -i "./本地视频.mp4" -c copy rtmp_addr # 使用 ffmpeg 推流
bili.send_dm("弹幕") # 发送弹幕
bili.stop_live() # 关闭直播间
```

