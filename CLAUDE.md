# CLAUDE.md

## 项目概述

B站直播自动推流系统，支持无人值守连续推流、弹幕监听、Telegram 远程管理。

## 技术栈

- Python 3.8+
- requests — B站 HTTP API
- aiohttp + brotli — 异步弹幕 WebSocket 客户端
- pure-protobuf — 弹幕消息 protobuf 解析
- python-telegram-bot 13.x — Telegram 机器人
- tomli — 配置文件解析（Python < 3.11）
- ffmpeg（外部依赖）— 视频推流

## 项目结构

```
main.py                  # 入口，多进程编排，支持 --local/--no-tg/--no-dm
config.toml.example      # 配置模板，复制为 config.toml 使用
utils/
  bilibili_api.py        # B站 API 封装（登录、WBI签名、开播、弹幕）
  config.py              # TOML 配置加载（带缓存）
  logger.py              # 结构化日志
  exceptions.py          # 自定义异常
blivedm/                 # 弹幕客户端（基于 xfgryujk/blivedm，MIT 协议）
  client.py              # 异步 WebSocket 客户端
  handlers.py            # 消息分发（含自定义事件：CUT_OFF/WARNING 等）
  models/                # 消息数据类
components/
  play_pipe.py           # 视频 → 命名管道
  play_server.py         # 命名管道 → B站 RTMP
  play_server_local.py   # 命名管道 → 本地 RTMP（测试）
  dmbot.py               # 弹幕监听与版权预警处理
  tg_bot.py              # Telegram 远程控制
tools/
  send_dm.py             # 手动发弹幕
  switcher.py            # 自动切换直播分区
```

## 架构要点

- **多进程模型**：main.py 以子进程启动各组件，崩溃自动重启
- **命名管道 IPC**：play_pipe 写入、play_server 读取，解耦视频读取与推流
- **qz_flag 信号机制**：通过 qz.log 文件传递版权预警停播信号
- **配置集中化**：所有参数在 config.toml，代码中无硬编码

## 已知陷阱

- **ffmpeg drawtext 冒号转义**：在 bash 中动态构建 filter_complex 时，drawtext text 参数中的 `\:` 会被双引号额外展开。正确做法是用单引号赋值给变量（`TIMETEXT='%{pts\:gmtime\:0\:%H\\\:%M\\\:%S}'`），再通过 `"$TIMETEXT"` 引用。绝不要在双引号字符串中直接写反斜杠转义序列。

## 开发约定

- 不提交 config.toml、data/、pipe/ 等运行时文件
- commit 消息不需要 co-author 信息
- blivedm/ 目录包含 MIT 许可证（原作者 xfgryujk），修改需保留 LICENSE
- 中文注释和日志
