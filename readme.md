# B站直播推流

B站直播自动推流系统，支持无人值守连续推流、弹幕监听、Telegram 远程管理。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 复制配置文件并填入你的信息
cp config.toml.example config.toml

# 使用二维码登录（首次使用）
python -c "from utils import BilibiliAPI; b = BilibiliAPI(); b.login_with_qrcode()"

# 启动（正常模式）
python main.py

# 本地测试模式（不连接 B 站，不启动弹幕和 Telegram）
python main.py --local

# 可选：不启动 Telegram 机器人
python main.py --no-tg

# 可选：不启动弹幕监听
python main.py --no-dm
```

启动后按 `Ctrl+C` 停止所有组件。

## 目录结构

```
push2live/
├── config.toml              # 统一配置文件（需自行创建，见 config.toml.example）
├── config.toml.example      # 配置文件模板
├── main.py                  # 统一入口
├── components/              # 核心组件
│   ├── play_pipe.py         # 读取视频文件，推流到管道
│   ├── play_server.py       # 从管道推流到 B 站 RTMP 服务器
│   ├── play_server_local.py # 从管道推流到本地 RTMP 服务器（测试用）
│   ├── dmbot.py             # 直播间弹幕监听与处理
│   └── tg_bot.py            # Telegram 机器人，远程管理与弹幕转发
├── tools/                   # 独立小工具（可单独运行）
│   ├── send_dm.py           # 手动发送弹幕
│   └── switcher.py          # 自动切换直播间分类
├── utils/                   # 工具库
│   ├── bilibili_api.py      # B 站 API 封装（登录、开播、推流地址、弹幕等）
│   ├── config.py            # 配置加载（读取 config.toml）
│   ├── logger.py            # 日志系统
│   └── exceptions.py        # 自定义异常
├── blivedm/                 # B 站弹幕处理库
├── data/                    # 数据文件
│   ├── cookie.json          # B 站登录 cookies
│   ├── videos.json          # 推流播放列表与进度
│   └── live.log             # 直播历史记录
└── pipe/                    # 管道文件目录
    └── pushlive             # 命名管道（防止推流断流）
```

## 推流流程

```
play_pipe（视频文件 → 管道） → play_server（管道 → B站 RTMP）→ B站直播间
                                                                    ↑
                                              dmbot（弹幕监听） ←──┘
                                              tg_bot（Telegram 转发）
```

## 配置说明

所有配置集中在 `config.toml` 中，主要分为：

- `[bilibili]` — 直播间 ID、分类、cookie 路径
- `[telegram]` — Bot Token 和群组 Chat ID
- `[ffmpeg]` — 推流编码参数（码率、音频等）
- `[local]` — 本地测试 RTMP 地址
- `[paths]` — 各数据文件路径
- `[switcher]` — 分类切换配置

