import os
import time
import logging
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram.utils.request import Request
from telegram.ext.dispatcher import run_async

from utils.bilibili_api import BilibiliAPI
from utils.config import load_config

_config = None
_bili = None
_bot = None


def start(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text='欢迎使用机器人！')


def handle_message(update: Update, context: CallbackContext):
    global _bili, _config
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else None
    group_chat_id = _config["telegram"]["chat_id"]

    if text is None:
        return

    reply_text = None

    if str(chat_id) == str(group_chat_id):
        pass
    else:
        if text == '/start':
            reply_text = '欢迎使用机器人！'
        elif text == '/start_live':
            _run_live()
        elif text == '/stop_live':
            _stop_live()
        elif text.startswith('/send '):
            try:
                ret = _bili.send_dm(text[6:])
                if ret is not None:
                    reply_text = '发送成功'
                else:
                    reply_text = '网络错误'
            except Exception:
                reply_text = '发送失败'
        else:
            reply_text = f'你发送了：{text}'

        if reply_text:
            context.bot.send_message(chat_id=chat_id, text=reply_text)


@run_async
def _run_live():
    global _config
    qz_flag_path = _config["paths"]["qz_flag"]
    with open(qz_flag_path, "w") as f:
        f.write("0")
    p = subprocess.Popen(f"python3 {ROOT_DIR}/components/play_server.py", shell=True)
    p.wait()


@run_async
def _stop_live():
    global _bili, _config
    qz_flag_path = _config["paths"]["qz_flag"]
    with open(qz_flag_path, "w") as f:
        f.write("1")
    _bili.stop_live()


def tail_f(log_file):
    log_file.seek(0, os.SEEK_END)
    while True:
        line = log_file.readline()
        if not line:
            time.sleep(0.1)
            continue
        yield line


def run(config=None):
    global _config, _bili, _bot
    if config is None:
        config = load_config()
    _config = config

    tg_config = config["telegram"]
    token = tg_config["bot_token"]
    group_chat_id = tg_config["chat_id"]
    dm_log_path = config["paths"]["dm_log"]

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    _bili = BilibiliAPI(config)
    _bili.login_with_cookie()

    proxy_url = tg_config.get("proxy", "")
    request_kwargs = {"proxy_url": proxy_url} if proxy_url else {}

    _bot = Bot(token=token, request=Request(**request_kwargs) if request_kwargs else None)

    updater = Updater(token=token, use_context=True, request_kwargs=request_kwargs)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_message))
    updater.start_polling()

    with open(dm_log_path, "r") as f:
        log_lines = tail_f(f)
        for line in log_lines:
            try:
                _bot.send_message(chat_id=group_chat_id, text=line.strip())
            except Exception as e:
                print(e)
            time.sleep(1)


if __name__ == '__main__':
    run()
