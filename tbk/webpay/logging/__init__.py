import os
import datetime

import pytz
from six.moves.urllib.parse import urlparse

__all__ = ['logger', 'BaseHandler', 'NullHandler']


LOG_DATE_FORMAT = "%d%m%Y"
LOG_TIME_FORMAT = "%H%M%S"


class BaseHandler(object):

    def event_payment(self, date, time, pid, commerce_id, transaction_id, request_ip, token, webpay_server):
        raise NotImplementedError("Logging Handler must implement event_payment")

    def configuration_payment(self, commerce_id, server_ip, server_port,
                              response_path, webpay_server, webpay_server_port):
        raise NotImplementedError("Logging Handler must implement configuration_payment")

    def event_confirmation(self, date, time, pid, commerce_id, transaction_id, request_ip, order_id):
        raise NotImplementedError("Logging Handler must implement event_confirmation")

    def log_confirmation(self, params, commerce_id):
        raise NotImplementedError("Logging Handler must implement log_confirmation")


class NullHandler(BaseHandler):

    def event_payment(self, **kwargs):
        pass

    def configuration_payment(self, **kwargs):
        pass

    def event_confirmation(self, **kwargs):
        pass

    def log_confirmation(self, **kwargs):
        pass


class Logger(object):

    def __init__(self, handler):
        self.set_handler(handler)

    def set_handler(self, handler):
        self.handler = handler

    def payment(self, payment):
        santiago = pytz.timezone('America/Santiago')
        now = santiago.localize(datetime.datetime.now())
        self.handler.event_payment(
            date=now.strftime(LOG_DATE_FORMAT),
            time=now.strftime(LOG_TIME_FORMAT),
            pid=os.getpid(),
            commerce_id=payment.commerce.id,
            transaction_id=payment.transaction_id,
            request_ip=payment.request_ip,
            token=payment.token(),
            webpay_server=self.get_webpay_server(payment.commerce)
        )
        response_uri = urlparse(payment.confirmation_url)
        self.handler.configuration_payment(
            commerce_id=payment.commerce.id,
            server_ip=response_uri.hostname,
            server_port=response_uri.port,
            response_path=response_uri.path,
            webpay_server=self.get_webpay_server(payment.commerce),
            webpay_server_port=self.get_webpay_port(payment.commerce)
        )

    def confirmation(self, confirmation):
        santiago = pytz.timezone('America/Santiago')
        now = santiago.localize(datetime.datetime.now())
        self.handler.event_confirmation(
            date=now.strftime(LOG_DATE_FORMAT),
            time=now.strftime(LOG_TIME_FORMAT),
            pid=os.getpid(),
            commerce_id=confirmation.commerce.id,
            transaction_id=confirmation.transaction_id,
            request_ip=confirmation.request_ip,
            order_id=confirmation.order_id,
        )
        self.handler.log_confirmation(
            params=confirmation.params,
            commerce_id=confirmation.commerce.id
        )

    def get_webpay_server(self, commerce):
        return 'https://certificacion.webpay.cl' if commerce.testing else 'https://webpay.transbank.cl'

    def get_webpay_port(self, commerce):
        return '6443' if commerce.testing else '433'

logger = Logger(NullHandler())


def configure_logger(handler):
    global logger
    logger.set_handler(handler)
