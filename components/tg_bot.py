import asyncio
import logging
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from utils.bilibili_api import BilibiliAPI
from utils.config import load_config

logger = logging.getLogger("tg_bot")


# ============ 权限检查 ============

def admin_only(func):
    """装饰器：仅允许 admin_ids 中的用户执行"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        admin_ids = context.bot_data.get("admin_ids", [])
        if admin_ids and update.effective_user.id not in admin_ids:
            await update.message.reply_text("无权限")
            return
        return await func(update, context)
    return wrapper


# ============ 命令处理 ============

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("欢迎使用推流控制机器人！\n"
                                    "/start_live - 恢复推流\n"
                                    "/stop_live - 停止推流\n"
                                    "/send <消息> - 发送弹幕")


@admin_only
async def cmd_start_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qz_flag_path = context.bot_data["qz_flag_path"]
    with open(qz_flag_path, "w") as f:
        f.write("0")
    await update.message.reply_text("已恢复推流信号（qz_flag=0），等待组件自动重启")


@admin_only
async def cmd_stop_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qz_flag_path = context.bot_data["qz_flag_path"]
    bili: BilibiliAPI = context.bot_data["bili"]
    with open(qz_flag_path, "w") as f:
        f.write("1")
    try:
        bili.stop_live()
        await update.message.reply_text("已停止推流并关闭直播间")
    except Exception as e:
        await update.message.reply_text(f"停止推流失败: {e}")


@admin_only
async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bili: BilibiliAPI = context.bot_data["bili"]
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("用法: /send <弹幕内容>")
        return
    try:
        ret = bili.send_dm(text)
        if ret is not None:
            await update.message.reply_text("发送成功")
        else:
            await update.message.reply_text("网络错误")
    except Exception:
        await update.message.reply_text("发送失败")


# ============ 弹幕转发 ============

async def forward_danmaku(app: Application, dm_log_path: str, chat_id: str):
    """异步监听弹幕日志，转发到 Telegram 群组"""
    # 等待日志文件存在
    while not os.path.exists(dm_log_path):
        await asyncio.sleep(2)

    with open(dm_log_path, "r") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                await asyncio.sleep(0.5)
                continue
            try:
                await app.bot.send_message(chat_id=chat_id, text=line.strip())
            except Exception as e:
                logger.warning(f"弹幕转发失败: {e}")
            await asyncio.sleep(1)


# ============ 入口 ============

def run(config=None):
    if config is None:
        config = load_config()

    tg_config = config["telegram"]
    token = tg_config["bot_token"]
    group_chat_id = str(tg_config["chat_id"])
    dm_log_path = config["paths"]["dm_log"]
    qz_flag_path = config["paths"]["qz_flag"]
    proxy_url = tg_config.get("proxy", "")

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    bili = BilibiliAPI(config)
    bili.login_with_cookie()

    # 构建 Application
    builder = Application.builder().token(token)
    if proxy_url:
        builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)
    app = builder.build()

    # 共享数据，替代全局变量
    app.bot_data["bili"] = bili
    app.bot_data["config"] = config
    app.bot_data["qz_flag_path"] = qz_flag_path
    app.bot_data["admin_ids"] = tg_config.get("admin_ids", [])

    # 注册命令
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("start_live", cmd_start_live))
    app.add_handler(CommandHandler("stop_live", cmd_stop_live))
    app.add_handler(CommandHandler("send", cmd_send))

    # 启动弹幕转发任务
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_all():
        async with app:
            await app.start()
            await app.updater.start_polling()
            # 并发运行弹幕转发
            await forward_danmaku(app, dm_log_path, group_chat_id)

    try:
        loop.run_until_complete(start_all())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    run()
