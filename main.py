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
        print(user)
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
                                    interactive_media.InteractiveMediaButton('view_events', 'Посмотреть мероприятия'),
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
                    date = datetime.datetime.strptime(message.strip(), '%d.%m.%Y')
                    today = datetime.datetime.strptime(datetime.date.today().strftime('%d.%m.%Y'), '%d.%m.%Y')
                    if datetime.datetime.timestamp(date) <= datetime.datetime.timestamp(today):
                        raise ValueError
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
                        'Дата должна быть в формате ДД.ММ.ГГГГ и быть в будущем.\n'
                        'Например, %s' % tomorrow_date
                    )
            elif state in ['add_event_members', 'add_event_feedback_error']:
                users = message.strip().split()
                self.bad = []
                good = []
                event_data = json.loads(user[4])
                print(event_data)
                event_name = str(event_data['event_name'])
                event_end_date = str(event_data['event_end_date'])
                event_feedback_type = str(event_data['event_feedback_type'])
                event_members = event_data['event_members'].split(', ') if 'event_members' in event_data.keys() else []
                if 'event_id' not in event_data.keys():
                    event_id = int(self.add_event(event_name, event_end_date, event_feedback_type))
                    event_data['event_id'] = event_id
                    self.set_state_info(user[0], event_data)
                else:
                    event_id = int(event_data['event_id'])
                for u in users:
                    peer = self.bot.users.find_user_outpeer_by_nick(u[1:] if u[0] == '@' else u)
                    if not peer.id:
                        self.bad.append(u)
                    elif user[4] != '':
                        good.append(u)
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
                                                'feedback_like_%s' % event_id,
                                                interactive_media.InteractiveMediaButton('feedback_like',
                                                                                         '\U0001F44D'),
                                                'primary'
                                            ),
                                            interactive_media.InteractiveMedia(
                                                'feedback_dislike_%s' % event_id,
                                                interactive_media.InteractiveMediaButton('feedback_dislike',
                                                                                         '\U0001F44E'),
                                                'primary'
                                            )
                                        ]
                                    )
                                ]
                            )
                        elif event_feedback_type == 'scale':
                            self.bot.messaging.send_message(
                                peer,
                                'Как ты оценишь этот ивент по школе от 1 до 5?\n'
                                '1 — очень плохо, 5 — очень хорошо',
                                [
                                    interactive_media.InteractiveMediaGroup(
                                        [
                                            interactive_media.InteractiveMedia(
                                                'feedback_%s_%s' % (i, event_id),
                                                interactive_media.InteractiveMediaButton('feedback_%s' % i,
                                                                                         '%s' % i),
                                                'primary'
                                            )
                                            for i in range(1, 6)
                                        ]
                                    )
                                ]
                            )
                self.add_event_members(int(event_data['event_id']), list(set(good + event_members)))
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
                        '%s' % ' '.join(self.bad),
                        again_buttons
                    )
                    self.set_state(user[0], 'add_event_feedback_error')
                else:
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        '\U00002705 Сообщения успешно отправлены.'
                    )
                    self.back_to_menu(user)
            elif state == 'view_events':
                data = self.get_events()
                example_event_id = data[0][0]
                event_ids = [i[0] for i in data]
                try:
                    event_id = int(message.strip())
                    if event_id not in event_ids:
                        raise ValueError
                    event = data[event_ids.index(event_id)]
                    feedback = self.get_feedback_from_db(event_id)
                    print(event, feedback)
                    today = int(datetime.datetime.timestamp(
                        datetime.datetime.strptime(datetime.date.today().strftime('%d.%m.%Y'), '%d.%m.%Y')))
                    end_date = datetime.datetime.fromtimestamp(1571962485).strftime('%d.%m.%Y')
                    if int(event[2]) <= today:
                        process = '\U0001F3C1 Сбор завершен *%s*' % end_date
                    else:
                        process = '\U0001F552 Сбор закончится *%s*' % end_date
                    feedback_type = '\U0001F44D / \U0001F44E' if event[3] == 'like_dislike' else 'оценка 1 — 5'
                    members = event[4].split(', ')
                    feedback_members = [['@' + str(i[1]), i[2]] for i in feedback]
                    if len(feedback_members) == 0:
                        feedback_list = 'Еще никто не оставил отзыв.'
                    else:
                        feedback_list = '\n'.join([i[0] + ': ' + '\U0001F44D' if i[1] == 'like' else
                                                   i[0] + ': ' + '\U0001F44E' if i[1] == 'dislike' else i[1]
                                                   for i in feedback_members] +
                                                  [i + ': —' for i in members if i not in [e[0]
                                                                                           for e in feedback_members]])
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        'Фидбэк по мероприятию *%s*\n'
                        '%s, тип: %s\n\n'
                        '%s' % (event[1], process, feedback_type, feedback_list)
                    )
                except ValueError:
                    self.bot.messaging.send_message(
                        self.bot.users.get_user_peer_by_id(user[0]),
                        'Номер ивента должен быть из списка выше!\n'
                        'Например, %s' % example_event_id
                    )

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
            elif value == 'view_events':
                data = self.get_events()
                events = []
                for i in range(len(data)):
                    today = int(datetime.datetime.timestamp(
                        datetime.datetime.strptime(datetime.date.today().strftime('%d.%m.%Y'), '%d.%m.%Y')))
                    emoji = ' \U0001F3C1' if int(data[i][2]) <= today else ''
                    s = str(data[i][0]) + '. ' + str(data[i][1]) + emoji
                    events.append(s)
                if len(events) == 0:
                    events.append('Здесь пока пусто.')
                buttons = [
                    interactive_media.InteractiveMediaGroup(
                        [
                            interactive_media.InteractiveMedia(
                                9,
                                interactive_media.InteractiveMediaButton('back_to_menu', 'Назад в меню')
                            )
                        ]
                    )
                ]
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    '*Для подробной информации пришли мне номер ивента*\n\n' + '\n'.join(events),
                    buttons
                )
                self.set_state(user[0], 'view_events')
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
            elif value == 'back_to_menu':
                self.back_to_menu(user)

        elif value.startswith('feedback_like') or value.startswith('feedback_dislike'):
            print('LIKE / DISLIKE FEEDBACK')
            print(params[0])
            feedback = params[0].id.split('_')[1:]
            self.add_feedback(user[0], int(feedback[1]), feedback[0])

        elif value.startswith('feedback_'):
            print('SCALE FEEDBACK')
            feedback = params[0].id.split('_')[1:]
            print(feedback)

    def get_user(self, uid):
        cur = self.con.cursor()
        user = cur.execute('SELECT * FROM users WHERE id = ? LIMIT 1', (int(uid),)).fetchone()
        if not user:
            username = str(self.bot.users.get_user_by_id(uid).data.nick.value)
            self.create_user(uid, username=username, role='user')
            self.con.commit()
            user = cur.execute('SELECT * FROM users WHERE id = ? LIMIT 1', (int(uid),)).fetchone()
        cur.close()
        return user if user else None

    def create_user(self, uid, username='', role='user'):
        cur = self.con.cursor()
        user = cur.execute('INSERT INTO users(id, username, role, state, state_info) VALUES (?, ?, ?, "menu", "");',
                           (int(uid), str(username), str(role))).fetchone()
        cur.close()
        return user if user else None

    def get_events(self, uid):
        cur = self.con.cursor()
        user = cur.execute('SELECT * FROM users WHERE id = ? LIMIT 1', (int(uid),)).fetchone()
        cur.close()
        return user if user else None

    def set_state(self, uid, state):
        cur = self.con.cursor()
        cur.execute('UPDATE users SET state = ? WHERE id = ?', (str(state), int(uid)))
        self.con.commit()
        cur.close()
        return True

    def set_state_info(self, uid, state_info):
        cur = self.con.cursor()
        cur.execute('UPDATE users SET state_info = ? WHERE id = ?', (str(state_info).replace("'", '"'), int(uid)))
        self.con.commit()
        cur.close()
        return True

    def add_event(self, event_name, event_end_date, event_feedback_type):
        date = datetime.datetime.timestamp(datetime.datetime.strptime(event_end_date, '%d.%m.%Y'))
        cur = self.con.cursor()
        cur.execute('INSERT INTO events (title, end_date, feedback_type) VALUES(?, ?, ?)',
                    (str(event_name), int(date), str(event_feedback_type)))
        row_id = cur.lastrowid
        cur.execute('CREATE TABLE event_%s(id INTEGER PRIMARY KEY, username TEXT, feedback TEXT)'
                    % row_id)
        self.con.commit()
        cur.close()
        return row_id

    def add_event_members(self, event_id, members):
        cur = self.con.cursor()
        cur.execute('UPDATE events SET members = ? WHERE id = ?',
                    (', '.join(members), int(event_id)))
        self.con.commit()
        cur.close()
        return True

    def get_events(self):
        cur = self.con.cursor()
        data = cur.execute('SELECT * FROM events').fetchall()
        cur.close()
        return data

    def get_feedback_from_db(self, event_id):
        cur = self.con.cursor()
        data = cur.execute('SELECT * FROM event_%s' % str(event_id)).fetchall()
        cur.close()
        return data

    def add_feedback(self, uid, event_id, feedback):
        cur = self.con.cursor()
        username = str(self.bot.users.get_user_by_id(uid).data.nick.value)
        today = datetime.datetime.strptime(datetime.date.today().strftime('%d.%m.%Y'), '%d.%m.%Y')
        today = datetime.datetime.timestamp(today)
        event_data = cur.execute('SELECT * FROM events WHERE id = ?', (str(event_id), )).fetchone()
        end_date = int(event_data[2]) if event_data else 0
        if not event_data or end_date <= today:
            print(event_data, end_date, today)
            self.bot.messaging.send_message(
                self.bot.users.get_user_peer_by_id(uid),
                'Фидбэк по этому мероприятию больше не принимается \U0001F614'
            )
        else:
            if not cur.execute('SELECT * FROM event_%s WHERE id = ?' % str(event_id), (int(uid), )).fetchone():
                cur.execute('INSERT INTO event_%s (id, username, feedback) VALUES (?, ?, ?)' % str(event_id),
                            (int(uid), username, str(feedback))).fetchall()
                self.con.commit()
            else:
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(uid),
                    'Ты уже оставляфл(а) фидбэк по этому ивенту.'
                )
        cur.close()
        return 1

    def back_to_menu(self, user):
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
                            interactive_media.InteractiveMediaButton('view_events',
                                                                     'Посмотреть мероприятия'),
                            'primary'
                        )
                    ]
                )
            ]
        )
        self.set_state(user[0], 'menu')
        self.set_state_info(user[0], '')


bot = Bot()
