import json
import logging
import os
import sys
import time
from http import HTTPStatus

from dotenv import load_dotenv
from telebot import TeleBot
import requests

from exceptions import (
    CustomAPIResponseError,
    HomeworkVerdictNotFound,
    TelegramError,
    JSONDecodeError)


load_dotenv()

logger = logging.getLogger(__name__)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
TIMEOUT = 10

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    missing_tokens = [name for name, value in tokens.items() if not value]
    for token in missing_tokens:
        logger.critical(f'Отсутствует переменная окружения: {token}')
    return not missing_tokens


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка {error}')
    if response.status_code != HTTPStatus.OK:
        raise CustomAPIResponseError(
            f'Неуспешный статус ответа API: {response.status_code}')
    try:
        return response.json()
    except json.JSONDecodeError as error:
        raise JSONDecodeError(
            f'Ошибка при декодировании JSON: {error}'
        )


def check_response(response):
    """
    Проверяет ответ API на соответствие документации.
    из урока «API сервиса Практикум Домашка».
    """
    if not isinstance(response, dict):
        raise TypeError(
            f'Неожиданный формат ответа: {type(response)}\n'
            f'Сообщение: {response}'
        )
    if 'homeworks' not in response:
        raise KeyError('В ответе нет ключа "homeworks"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(f'Формат ответа не список, получен {type(homeworks)}.')
    return homeworks


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе её статус."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise HomeworkVerdictNotFound(
            'Неизвестный статус домашней работы "{status}". '
            'Бот работает со следующими статусами: '
            f'{", ".join(HOMEWORK_VERDICTS.keys())}.'
        )

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramError as telegram_error:
        logger.error(f'Сбой при отправке сообщения: {telegram_error}')
    except Exception as other_error:
        logger.error(f'Другая ошибка при отправке сообщения: {other_error}')
    else:
        logger.debug(f'Сообщение отправлено: {message}')


def main():  # noqa
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует хотя бы одна переменная окружения')
        sys.exit('Аварийный выход, ошибка!')

    logger.debug('Переменные окружения доступны')
    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response.get('current_date', timestamp)
            if not homeworks:
                message = 'Нет новых статусов домашних работ.'
                logger.info(message)
            else:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                logger.info(message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            try:
                send_message(bot, message)
            except TelegramError as tg_error:
                logger.error(
                    f'Не удалось отправить сообщение в телегу: {tg_error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - [%(levelname)s] - %(name)s - '
               '(%(filename)s).%(funcName)s(%(lineno)d) - %(message)s',
        handlers=[
            logging.FileHandler("program.log"),
            logging.StreamHandler()  # Логи выводятся в консоль
        ]
    )
    logger.debug('Начало работы бота')
    main()
