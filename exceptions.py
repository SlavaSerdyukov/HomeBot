class CustomAPIResponseError(Exception):
    """Исключение для неуспешного статуса ответа API."""

    pass


class HomeworkVerdictNotFound(ValueError):
    """Не верный статус домашней работы."""

    pass


class NotForSendingError(Exception):
    """общий класс ошибок, которые не посылаем в телегу."""

    pass


class TelegramError(NotForSendingError):
    """Вылетает когда не получилось выслать в телегу."""

    pass


class JSONDecodeError(Exception):
    """Исключение для ошибок при декодировании JSON."""

    pass
