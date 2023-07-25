from time import sleep
import colorama
from colorama import Fore, Style
from ping3 import *
from datetime import datetime
import telebot
import config


TOKEN = config.TOKEN
bot = telebot.TeleBot(TOKEN)
sup_chat = config.sup_chat
colorama.init()
timelog = datetime.now().strftime("%d.%m.%y %H:%M:%S")


def pings(ip):
    return ping(ip, unit='ms')


def problem(name, res):
    if res is None:
        result = f'⚠{name}: Превышено время ожидания ответа!'
    elif res is False:
        result = f'⛔{name}: Недоступен!'
    else:
        result = f'⁉{name}: Неизвестная проблема!'

    ans = (Fore.RED + "Недоступен" + Style.RESET_ALL)
    print(f'{name}: {ans};\n')
    with open('Logs.txt', 'a') as file:
        file.write(f'{timelog}: {name}: {res}\n')
    try:
        bot.send_message(sup_chat, text=result)
    except Exception as e:
        print("Неудалось отправить сообщение в Телеграм!\n"
              f"Ошибка: {e}\n")
        with open('Logs.txt', 'a') as file:
            file.write(f'{timelog}: Неудалось отправить сообщение в Телеграм!\n')


def done(name, p):
    ans = (Fore.GREEN + "Доступен" + Style.RESET_ALL)
    print(f'{name}: {ans}, время отклика: {round(p)} мс;\n')


def main():
    while True:
        with open('servers.txt', 'r') as file:
            for f in file:
                servers = f.replace(' ', '').split(',')
        print(timelog)
        for server in servers:
            res = pings(server)
            if isinstance(res, float):
                done(server, res)
            else:
                problem(server, res)
        sleep(60)


if __name__ == '__main__':
    main()
