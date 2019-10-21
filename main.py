from dialog_bot_sdk.bot import DialogBot
from dialog_bot_sdk import interactive_media
import grpc
import os
import sqlite3
from dotenv import load_dotenv
import json
import datetime


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
        user = self.get_user(params[0].sender_uid)
        message = str(params[0].message.textMessage.text)
        if user:
            state = user[3]
        else:
            self.create_user(params[0].sender_uid)
            state = 'menu'

        if user[2] == 'admin':
            if message == '/start':
                self.set_state(user[0], 'menu')
                self.bot.messaging.send_message(
                    params[0].peer,
                    '\U0001F44B Привет!\nЯ — бот для удобного сбора фидбэка с мероприятий.',
                    [
                        interactive_media.InteractiveMediaGroup(
                            [
                                interactive_media.InteractiveMedia(
                                    1,
                                    interactive_media.InteractiveMediaButton('add_event', 'Добавить мероприятие'),
                                    'primary'
                                ),
                                interactive_media.InteractiveMedia(
                                    2,
                                    interactive_media.InteractiveMediaButton('view_event', 'Посмотреть мероприятия'),
                                    'primary'
                                )
                            ]
                        )
                    ]
                )
            elif state == 'add_event_name':
                state_info = json.dumps({'event_name': message})
                self.set_state_info(user[0], state_info)
                tomorrow_date = (datetime.date.today() + datetime.timedelta(days=2)).strftime('%d.%m.%Y')
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    'Отлично! Теперь пришли мне дату окончания сбора фидбэка.\n'
                    'Например, %s' % str(tomorrow_date)
                )
                self.set_state(user[0], 'add_event_end_date')
            elif state == 'add_event_end_date':
                tomorrow_date = (datetime.date.today() + datetime.timedelta(days=2)).strftime('%d.%m.%Y')
                try:
                    datetime.datetime.strptime(message.strip(), '%d.%m.%Y')
                    state_info = json.loads(user[4])
                    state_info['event_end_date'] = message.strip()
                    self.set_state_info(user[0], json.dumps(state_info))
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        'Класс! Выбери тип фидбэка',
                        [
                            interactive_media.InteractiveMediaGroup(
                                [
                                    interactive_media.InteractiveMedia(
                                        3,
                                        interactive_media.InteractiveMediaButton('feedback_type_like_dislike',
                                                                                 '\U0001F44D / \U0001F44E'),
                                        'primary'
                                    ),
                                    interactive_media.InteractiveMedia(
                                        4,
                                        interactive_media.InteractiveMediaButton('feedback_type_scale',
                                                                                 'Шкала от 1 до 5'),
                                        'primary'
                                    )
                                ]
                            )
                        ]
                    )
                    self.set_state(user[0], 'add_event_feedback_type')
                except ValueError:
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        'Дата должны быть в формате ДД.ММ.ГГГГ.\n'
                        'Например, %s' % tomorrow_date
                    )

    def on_click(self, *params):
        user = self.get_user(params[0].uid)
        value = params[0].value

        if value == 'add_event':
            if user[2] == 'admin':
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    '*Добавление мероприятия*\n'
                    'Введи название ивента'
                )
                self.set_state(user[0], 'add_event_name')

    def get_user(self, uid):
        cur = self.con.cursor()
        user = cur.execute('SELECT * FROM users WHERE id = ? LIMIT 1', (int(uid),)).fetchone()
        cur.close()
        return user if user else None

    def create_user(self, uid, username='', role='user'):
        cur = self.con.cursor()
        user = cur.execute('INSERT INTO users(id, username, role) VALUES (?, "?", "?");', (int(uid), str(username), str(role))).fetchone()
        cur.close()
        return user if user else None

    def get_events(self, uid):
        cur = self.con.cursor()
        user = cur.execute('SELECT * FROM users WHERE id = ? LIMIT 1', (int(uid),)).fetchone()
        cur.close()
        return user if user else None

    def set_state(self, uid, state):
        cur = self.con.cursor()
        cur.execute('UPDATE users SET state = ? WHERE id = ?', (str(state), int(uid),))
        self.con.commit()
        cur.close()
        return True

    def set_state_info(self, uid, state_info):
        cur = self.con.cursor()
        cur.execute('UPDATE users SET state_info = ? WHERE id = ?', (str(state_info), int(uid),))
        self.con.commit()
        cur.close()
        return True


bot = Bot()
