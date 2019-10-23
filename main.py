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
        self.bad = []
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
                    '\U0001F44B Привет!\n'
                    'Я — бот для удобного сбора фидбэка с мероприятий.',
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
                                                                                 'Оценка от 1 до 5'),
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
                        'Дата должна быть в формате ДД.ММ.ГГГГ\n'
                        'Например, %s' % tomorrow_date
                    )
            elif state in ['add_event_members', 'add_event_feedback_error']:
                users = message.strip().split()
                self.bad = []
                for u in users:
                    peer = self.bot.users.find_user_outpeer_by_nick(u[1:] if u[0] == '@' else u)
                    if not peer.id:
                        self.bad.append(u)
                    elif user[4] != '':
                        event_data = json.loads(user[4])
                        event_name = str(event_data['event_name'])
                        event_feedback_type = str(event_data['event_feedback_type'])
                        self.bot.messaging.send_message(
                            peer,
                            '\U0001F44B Привет!\n'
                            'Ты принимал(а) участие в мероприятии *%s*.\n'
                            'Пожалуйста, оставь небольшой фидбэк. Это не займет много времени.' % event_name
                        )
                        if event_feedback_type == 'like_dislike':
                            self.bot.messaging.send_message(
                                peer,
                                'Тебе понравилось?',
                                [
                                    interactive_media.InteractiveMediaGroup(
                                        [
                                            interactive_media.InteractiveMedia(
                                                'event_%s' % ''.join(event_name.lower()),
                                                interactive_media.InteractiveMediaButton('feedback_like',
                                                                                         '\U0001F44D'),
                                                'primary'
                                            ),
                                            interactive_media.InteractiveMedia(
                                                6,
                                                interactive_media.InteractiveMediaButton('feedback_dislike',
                                                                                         '\U0001F44E'),
                                                'primary'
                                            )
                                        ]
                                    )
                                ]
                            )
                again_buttons = [
                    interactive_media.InteractiveMediaGroup(
                        [
                            interactive_media.InteractiveMedia(
                                6,
                                interactive_media.InteractiveMediaButton('feedback_error_fix',
                                                                         'Исправить'),
                                'primary'
                            ),
                            interactive_media.InteractiveMedia(
                                5,
                                interactive_media.InteractiveMediaButton('feedback_error_skip',
                                                                         'Пропустить'),
                                'danger'
                            )
                        ]
                    )
                ]
                if len(self.bad) == 1:
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        '\U0001F6A7 Пользователю %s не удалось отправить сообщение.\n'
                        'Возможно, допущена ошибка в никнейме или такого пользователя не существует \U0001F937'
                        '' % self.bad[0],
                        again_buttons
                    )
                    self.set_state(user[0], 'add_event_feedback_error')
                elif len(self.bad) > 1:
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        '\U0001F6A7 Некоторым пользователям не удалось отправить сообщение.\n'
                        'Возможно, допущены ошибки в никнеймах или таких пользователей не существует \U0001F937\n\n'
                        '%s' % ' ' .join(self.bad),
                        again_buttons
                    )
                    self.set_state(user[0], 'add_event_feedback_error')
                else:
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        '\U00002705 Сообщения успешно отправлены.'
                    )
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        'Главное меню',
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
                                        interactive_media.InteractiveMediaButton('view_event',
                                                                                 'Посмотреть мероприятия'),
                                        'primary'
                                    )
                                ]
                            )
                        ]
                    )
                    self.set_state(user[0], 'menu')

    def on_click(self, *params):
        user = self.get_user(params[0].uid)
        state = user[3]
        value = params[0].value
        if user[2] == 'admin':
            if value == 'add_event':
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    '*Добавление мероприятия*\n'
                    'Введи название ивента'
                )
                self.set_state(user[0], 'add_event_name')
            elif value in ['feedback_type_like_dislike', 'feedback_type_scale']:
                state_info = json.loads(user[4])
                state_info['event_feedback_type'] = value[14:]
                self.set_state_info(user[0], json.dumps(state_info))
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    'Супер! Остался последний шаг: напиши через пробел никнеймы всех участников.\n'
                    'Им придет сообщение с просьбой оставить фидбэк.\n'
                    'Например, так: @bixnel @albinskiy'
                )
                self.set_state(user[0], 'add_event_members')
            elif state == 'add_event_feedback_error':
                if value == 'feedback_error_skip':
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        '\U00002705 Сообщения успешно отправлены.'
                    )
                elif value == 'feedback_error_fix':
                    if len(self.bad) == 1:
                        self.bot.messaging.send_message(
                            self.bot.users.get_user_peer_by_id(user[0]),
                            'Ок, пришли правильный никнейм для пользователя %s\n' % self.bad[0], ''
                        )
                    elif len(self.bad) > 1:
                        self.bot.messaging.send_message(
                            self.bot.users.get_user_peer_by_id(user[0]),
                            'Ок, пришли через пробел правильные никнеймы для пользователей:\n'
                            '%s' % ' '.join(self.bad)
                        )

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
