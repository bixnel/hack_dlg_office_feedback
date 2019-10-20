from dialog_bot_sdk.bot import DialogBot
from dialog_bot_sdk import interactive_media
import grpc
import os
import sqlite3
from dotenv import load_dotenv


class Bot:
    def __init__(self):
        load_dotenv('.env')
        self.con = sqlite3.connect('db.db', check_same_thread=False)
        self.bot = DialogBot.get_secure_bot(
            os.environ.get('BOT_ENDPOINT'),
            grpc.ssl_channel_credentials(),
            os.environ.get('BOT_TOKEN')
        )
        self.bot.messaging.on_message_async(self.on_msg, self.on_click)

    def on_msg(self, *params):
        cur = self.con.cursor()
        user = self.get_user(params[0].sender_uid, )
        message = str(params[0].message.textMessage.text)

        if user[2] == 'admin':
            if message == '/start':
                self.bot.messaging.send_message(
                    params[0].peer,
                    '\U0001F44B Привет!\nЯ — бот для удобного сбора фидбэка.',
                    [
                        interactive_media.InteractiveMediaGroup(
                            [
                                interactive_media.InteractiveMedia(
                                    1,
                                    interactive_media.InteractiveMediaButton('add_event', 'Добавить мероприятие'),
                                    'primary'
                                )
                            ]
                        ),
                        interactive_media.InteractiveMediaGroup(
                            [
                                interactive_media.InteractiveMedia(
                                    1,
                                    interactive_media.InteractiveMediaButton('view_event', 'Посмотреть мероприятия'),
                                    'primary'
                                )
                            ]
                        )
                    ]

                )

    def on_click(self, *params):
        print(params)

    def get_user(self, uid):
        cur = self.con.cursor()
        user = cur.execute('SELECT * FROM users WHERE id = ? LIMIT 1', (int(uid),)).fetchone()
        cur.close()
        return user if user else None


bot = Bot()
