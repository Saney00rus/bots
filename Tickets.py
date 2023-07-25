import threading
import requests
import xml.etree.ElementTree as ET
import telebot
import html
import schedule
import time
from telebot import types
import pickle
from cryptography.fernet import Fernet
import config

# Получаем ключ для шифрования
key = config.key

cipher_suite = Fernet(key)

# Читаем зашифрованные данные из файла
with open("encrypted_data.txt", "rb") as file:
    lines = file.readlines()
    encrypted_username = lines[0].strip()
    encrypted_password = lines[1].strip()
    encrypted_token = lines[2].strip()

# Дешифруем данные
decrypted_username = cipher_suite.decrypt(encrypted_username).decode()
decrypted_password = cipher_suite.decrypt(encrypted_password).decode()
decrypted_token = cipher_suite.decrypt(encrypted_token).decode()

bot_token = decrypted_token
# chat_id = '-1001847177692' #Тестовый
# chat_id = '167749311' #Мой
chat_id = '-1001836398372'

bot = telebot.TeleBot(bot_token)

url = 'http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API'
session_id = None
usertick = {"tg_id": ["tickets"]}

try:
    with open('processed_tickets.pkl', 'rb') as f:
        processed_tickets = pickle.load(f)
except FileNotFoundError:
    processed_tickets = set()


def tickets():
    # Создание SOAP-запроса для метода TicketSearch с использованием Session ID
    ticket_search_request = f'''
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API">
        <soap:Header/>
        <soap:Body>
            <tns:TicketSearch>
                <SessionID>{session_id}</SessionID>
                <State>new</State>
                <StateID>1</StateID>
                <StateType>new</StateType>
            </tns:TicketSearch>
        </soap:Body>
    </soap:Envelope>
    '''

    # Отправка SOAP-запроса TicketSearch
    ticket_search_response = requests.post(url, data=ticket_search_request, headers={'Content-Type': 'text/xml'})

    # Получение XML-ответа TicketSearch
    ticket_search_xml = ticket_search_response.content.decode()

    # Парсинг XML-ответа
    root = ET.fromstring(ticket_search_xml)

    # Извлечение TicketID каждой заявки
    return root


def close_sessions(user_login):
    # Создание SOAP-запроса для метода SessionClose
    session_close_request = f'''
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API">
       <soapenv:Header/>
       <soapenv:Body>
          <tns:SessionClose>
             <UserLogin>{user_login}</UserLogin>
          </tns:SessionClose>
       </soapenv:Body>
    </soapenv:Envelope>
    '''

    # Отправка SOAP-запроса SessionClose
    headers = {'Content-Type': 'text/xml'}
    response = requests.post(url, data=session_close_request, headers=headers)
    print(response)

    # Обработка ответа
    if response.status_code == 200:
        session_close_xml = response.content.decode()
        root = ET.fromstring(session_close_xml)
        # Проверка успешного закрытия сессии
        success_element = root.find('.//{http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API}Success')
        if success_element is not None and success_element.text == '1':
            print('Успешное закрытие сессий.')
        else:
            error_element = root.find('.//{http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API}Error')
            error_code = error_element.find(
                './/{http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API}ErrorCode').text
            error_message = error_element.find(
                './/{http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API}ErrorMessage').text
            print(f'Ошибка при закрытии сессий. Код ошибки: {error_code}, Сообщение ошибки: {error_message}')
    else:
        print('Ошибка при отправке SOAP-запроса.')


@bot.message_handler(commands=['start'])
def start(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button1 = types.KeyboardButton('/show_tickets')
    button2 = types.KeyboardButton('/show_my_tickets')
    keyboard.add(button1, button2)
    bot.reply_to(message, "Привет! Я бот для работы с заявками.", reply_markup=keyboard)


@bot.message_handler(commands=['show_tickets'])
def show_tickets(message):
    try:
        root = tickets()
        namespace = {'tns': 'http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API'}
        ticket_ids = root.findall('.//tns:TicketID', namespace)
        if len(ticket_ids) > 0:
            for ticket_id in ticket_ids:
                ticket_get_request = f'''
                    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API">
                        <soap:Header/>
                        <soap:Body>
                            <tns:TicketGet>
                                <SessionID>{session_id}</SessionID>
                                <TicketID>{ticket_id.text}</TicketID>
                                <AllArticles>?</AllArticles>
                            </tns:TicketGet>
                        </soap:Body>
                    </soap:Envelope>
                    '''

                # Отправка SOAP-запроса TicketGet
                ticket_get_response = requests.post(url, data=ticket_get_request, headers={'Content-Type': 'text/xml'})
                # print(ticket_get_response.text)

                # Получение XML-ответа TicketGet
                ticket_get_xml = ticket_get_response.content.decode()

                # Парсинг XML-ответа TicketGet
                ticket_root = ET.fromstring(ticket_get_xml)

                # Извлечение информации о заявке
                ticket_data = ticket_root.find('.//tns:Ticket', namespace)

                # Вывод информации о заявке
                ticket_id = ticket_data.find('tns:TicketID', namespace).text
                created = ticket_data.find('tns:Created', namespace).text
                title = ticket_data.find('tns:Title', namespace).text
                body = ticket_data.find('tns:Article/tns:Body', namespace).text
                fromname = ticket_data.find('tns:Article/tns:FromRealname', namespace).text

                # Проверка на None перед экранированием неподдерживаемых тегов
                ticket_id = html.escape(ticket_id)
                created = html.escape(created)
                title = html.escape(title) if title else ''
                body = html.escape(body)
                fromname = html.escape(fromname)

                message_text = f'<pre><b>🔔 ЗАЯВКА №{ticket_id}</b>\n\n</pre>' \
                               f'<b>Отправитель:</b> {fromname}\n\n' \
                               f'<b>Создана:</b> {created}\n\n' \
                               f'<b>Заголовок:</b> {title}\n\n' \
                               f'<b>Описание:</b>\n<pre>{body}</pre>'

                bot.send_message(message.chat.id, message_text, parse_mode='HTML')

                # Добавляем заявку в обработанные
                processed_tickets.add(ticket_id)
                with open('processed_tickets.pkl', 'wb') as f:
                    pickle.dump(processed_tickets, f)

        else:
            bot.send_message(message.chat.id, 'Нет активных заявок.')
            start_bot()

    except Exception as e:
        # В случае возникновения ошибки, перезапускаем программу
        print(f"An error occurred: {e}")
        schedule.every(5).seconds.do(start_bot)


def check_new_tickets():
    try:
        global session_id, processed_tickets
        if session_id:
            root = tickets()
            namespace = {'tns': 'http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API'}
            ticket_ids = root.findall('.//tns:TicketID', namespace)

            if len(ticket_ids) > 0:
                for ticket_id in ticket_ids:
                    # Проверяем, есть ли заявка в обработанных
                    if ticket_id.text not in processed_tickets:
                        ticket_get_request = f'''
                            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API">
                                <soap:Header/>
                                <soap:Body>
                                    <tns:TicketGet>
                                        <SessionID>{session_id}</SessionID>
                                        <TicketID>{ticket_id.text}</TicketID>
                                        <AllArticles>?</AllArticles>
                                    </tns:TicketGet>
                                </soap:Body>
                            </soap:Envelope>
                            '''

                        # Отправка SOAP-запроса TicketGet
                        ticket_get_response = requests.post(url, data=ticket_get_request,
                                                            headers={'Content-Type': 'text/xml'})
                        # print(ticket_get_response.text)

                        # Получение XML-ответа TicketGet
                        ticket_get_xml = ticket_get_response.content.decode()

                        # Парсинг XML-ответа TicketGet
                        ticket_root = ET.fromstring(ticket_get_xml)

                        # Извлечение информации о заявке
                        ticket_data = ticket_root.find('.//tns:Ticket', namespace)

                        # Вывод информации о заявке
                        ticket_id = ticket_data.find('tns:TicketID', namespace).text
                        created = ticket_data.find('tns:Created', namespace).text
                        title = ticket_data.find('tns:Title', namespace).text
                        body = ticket_data.find('tns:Article/tns:Body', namespace).text
                        fromname = ticket_data.find('tns:Article/tns:FromRealname', namespace).text

                        # Проверка на None перед экранированием неподдерживаемых тегов
                        ticket_id = html.escape(ticket_id)
                        created = html.escape(created)
                        title = html.escape(title) if title else ''
                        body = html.escape(body)
                        fromname = html.escape(fromname)

                        message_text = f'<pre><b>🆕 НОВАЯ ЗАЯВКА №{ticket_id}</b>\n\n</pre>' \
                                       f'<b>Отправитель:</b> {fromname}\n\n' \
                                       f'<b>Создана:</b> {created}\n\n' \
                                       f'<b>Заголовок:</b> {title}\n\n' \
                                       f'<b>Описание:</b>\n<pre>{body}</pre>'

                        # Создание кнопки "Принять"
                        accept_button = types.InlineKeyboardButton('Принять',
                                                                   callback_data=f'accept_ticket:{ticket_id}')

                        # Создание клавиатуры с кнопкой
                        keyboard = types.InlineKeyboardMarkup()
                        keyboard.add(accept_button)

                        # Отправка сообщения с кнопкой
                        bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')

                        # Добавляем заявку в обработанные
                        processed_tickets.add(ticket_id)
                        with open('processed_tickets.pkl', 'wb') as f:
                            pickle.dump(processed_tickets, f)

            else:
                print('Нет активных заявок.')
                start_bot()
    except Exception as e:
        # В случае возникновения ошибки, перезапускаем программу
        print(f"An error occurred: {e}")
        schedule.every(5).seconds.do(start_bot)


# Обработка нажатий на кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_button_click(call):
    if call.data.startswith('accept_ticket:'):
        ticket_id = call.data.split(':')[1]
        user_id = call.from_user.id
        username = call.from_user.first_name

        # Обновление сообщения с информацией о заявке
        message_text = call.message.html_text
        message_text += f'\n\n<b>Принял в работу:</b> {username}'

        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text=message_text,
                              parse_mode='HTML')

        # Дополнительные действия по обработке заявки
        # ...
        if user_id in usertick:
            usertick[user_id].append(ticket_id)
        else:
            usertick[user_id] = [ticket_id]

        # Отправка уведомления пользователю
        bot.send_message(user_id, f'Вы приняли заявку №{ticket_id}')


def start_bot():
    global session_id
    try:
        # Закрытие текущей сессии, если она существует
        close_sessions(decrypted_username)
        # Создание SOAP-запроса для метода UserLogin
        user_login_request = f'''
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API">
            <soap:Header/>
            <soap:Body>
                <tns:SessionCreate>
                    <UserLogin>{decrypted_username}</UserLogin>
                    <Password>{decrypted_password}</Password>
                </tns:SessionCreate>
            </soap:Body>
        </soap:Envelope>
        '''

        # Отправка SOAP-запроса UserLogin
        user_login_response = requests.post(url, data=user_login_request, headers={'Content-Type': 'text/xml'})

        # Получение XML-ответа UserLogin
        user_login_xml = user_login_response.content.decode()

        # Парсинг XML-ответа UserLogin
        root = ET.fromstring(user_login_xml)

        # Извлечение SessionID из XML-ответа
        namespace = {'tns': 'http://otrs.12kdc.loc/otrs/nph-genericinterface.pl/Webservice/API'}
        session_id_element = root.find('.//tns:SessionID', namespace)
        if session_id_element is not None:
            session_id = session_id_element.text
            print('Успешная авторизация.')
        else:
            print('Ошибка авторизации.')
            schedule.every(60).seconds.do(start_bot)

        # Запуск планировщика задач для проверки новых заявок каждую минуту
        schedule.every(5).seconds.do(check_new_tickets)

        # Запуск бесконечного цикла для выполнения задач планировщика
        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        print(f'Произошла ошибка: {str(e)}')
        schedule.every(60).seconds.do(start_bot)


# Запуск бота в отдельном потоке
bot_thread = threading.Thread(target=bot.polling, daemon=True)
bot_thread.start()

# Запуск приложения
if __name__ == '__main__':
    while True:
        try:
            start_bot()
        except Exception as e:
            print(f'Произошла ошибка: {str(e)}')
