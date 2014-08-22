import sys
from unittest import TestCase

import mock

from tbk.webpay import Payment, TBK_VERSION_KCC, PaymentError


class PaymentTest(TestCase):

    def setUp(self):
        self.payment_kwargs = {
            'request_ip': '123.123.123.123',
            'commerce': mock.Mock(),
            'success_url': 'http://localhost:8080/webpay/success/',
            'confirmation_url': 'http://127.0.0.1:8080/webpay/confirmation/',
            'failure_url': 'http://localhost:8080/webpay/failure/',
            'session_id': 'SOME_SESSION_VALUE',
            'amount': 123456,
            'order_id': 1,
        }

    def test_initialize_with_all_args(self):
        """
        Create Payment with all it's args
        """
        payment = Payment(**self.payment_kwargs)
        self.assertEqual(payment.commerce, self.payment_kwargs['commerce'])
        self.assertEqual(payment.request_ip, self.payment_kwargs['request_ip'])
        self.assertEqual(payment.amount, self.payment_kwargs['amount'])
        self.assertEqual(payment.order_id, self.payment_kwargs['order_id'])
        self.assertEqual(
            payment.success_url, self.payment_kwargs['success_url'])
        self.assertEqual(payment.confirmation_url, self.payment_kwargs['confirmation_url'])
        self.assertEqual(payment.session_id, self.payment_kwargs['session_id'])
        self.assertEqual(
            payment.failure_url, self.payment_kwargs['failure_url'])

    @mock.patch('tbk.webpay.payment.Commerce.create_commerce')
    def test_initialize_without_commerce(self, create_commerce):
        """
        Create Payment and it uses default commerce from create_commerce
        """
        del self.payment_kwargs['commerce']
        payment = Payment(**self.payment_kwargs)
        self.assertEqual(payment.commerce, create_commerce.return_value)
        create_commerce.assert_called_once_with(None)

    @mock.patch('tbk.webpay.payment.Commerce.create_commerce')
    def test_initialize_without_commerce_but_config(self, create_commerce):
        """
        Create Payment and it uses commerce from create_commerce with config
        """
        config = mock.Mock()
        del self.payment_kwargs['commerce']
        self.payment_kwargs['config'] = config
        payment = Payment(**self.payment_kwargs)
        self.assertEqual(payment.commerce, create_commerce.return_value)
        create_commerce.assert_called_once_with(config)

    def test_initialize_without_failure_url(self):
        """
        Create Payment and it sets failure_url as success_url
        """
        del self.payment_kwargs['failure_url']
        payment = Payment(**self.payment_kwargs)

        self.assertEqual(
            payment.failure_url, self.payment_kwargs['success_url'])

    def test_initialize_without_session_id(self):
        """
        Create Payment and it sets session_id to None
        """
        del self.payment_kwargs['session_id']
        payment = Payment(**self.payment_kwargs)

        self.assertIsNone(payment.session_id)

    @mock.patch('tbk.webpay.payment.Payment.process_url')
    @mock.patch('tbk.webpay.payment.Payment.token')
    def test_redirect_url(self, token, process_url):
        """
        payment.redirect_url must return the url to redirect using process_url and token methods.
        """
        payment = Payment(**self.payment_kwargs)
        redirect_url = "%(process_url)s?TBK_VERSION_KCC=%(tbk_version)s&" \
            "TBK_TOKEN=%(token)s"
        expected = redirect_url % {
            'process_url': process_url.return_value,
            'tbk_version': TBK_VERSION_KCC,
            'token': token.return_value
        }
        self.assertEqual(expected, payment.redirect_url)

    def test_process_url_development(self):
        """
        payment.process_url on dev must return https://certificacion.webpay.cl:6443/filtroUnificado/bp_revision.cgi
        """
        commerce = mock.Mock()
        commerce.testing = True
        self.payment_kwargs['commerce'] = commerce
        payment = Payment(**self.payment_kwargs)

        self.assertEqual(
            "https://certificacion.webpay.cl:6443/filtroUnificado/bp_revision.cgi",
            payment.process_url()
        )

    def test_process_url_production(self):
        """
        payment.process_url on prod must return https://webpay.transbank.cl:443/filtroUnificado/bp_revision.cgi
        """
        commerce = mock.Mock()
        commerce.testing = False
        self.payment_kwargs['commerce'] = commerce
        payment = Payment(**self.payment_kwargs)

        self.assertEqual(
            "https://webpay.transbank.cl:443/filtroUnificado/bp_revision.cgi",
            payment.process_url()
        )

    @mock.patch('tbk.webpay.payment.Payment.fetch_token')
    @mock.patch('tbk.webpay.payment.logger')
    def test_token_not_created(self, logger, fetch_token):
        """
        payment.token must return a token from fetch_token and log
        """
        payment = Payment(**self.payment_kwargs)

        self.assertEqual(
            fetch_token.return_value,
            payment.token()
        )
        logger.payment.assert_called_once_with(payment)

    @mock.patch('tbk.webpay.payment.Payment.fetch_token')
    @mock.patch('tbk.webpay.payment.logger')
    def test_token_created(self, logger, fetch_token):
        """
        payment.token must return a token already fetched by fetch_token and dont log
        """
        payment = Payment(**self.payment_kwargs)
        token = payment.token()

        fetch_token.reset_mock()
        logger.reset_mock()

        self.assertEqual(
            token,
            payment.token()
        )
        self.assertFalse(fetch_token.called)
        self.assertFalse(logger.payment.called)

    @mock.patch('tbk.webpay.payment.requests')
    @mock.patch('tbk.webpay.payment.Payment.process_url')
    @mock.patch('tbk.webpay.payment.Payment.params')
    def test_fetch_token(self, params, process_url, requests):
        """
        payment.fetch_token must post data to process_url and get token from response
        """
        python_version = "%d.%d" % (sys.version_info.major, sys.version_info.minor)
        user_agent = "TBK/%(TBK_VERSION_KCC)s (Python/%(PYTHON_VERSION)s)" % {
            'TBK_VERSION_KCC': TBK_VERSION_KCC,
            'PYTHON_VERSION': python_version
        }
        commerce = self.payment_kwargs['commerce']
        payment = Payment(**self.payment_kwargs)
        response = requests.post.return_value
        response.status_code = 200
        decrypted = {'body': 'TOKEN=aA123,ERROR=0'}
        commerce.webpay_decrypt.return_value = decrypted

        token = payment.fetch_token()

        requests.post.assert_called_once_with(
            process_url.return_value,
            data={
                'TBK_VERSION_KCC': TBK_VERSION_KCC,
                'TBK_CODIGO_COMERCIO': commerce.id,
                'TBK_KEY_ID': commerce.webpay_key_id,
                'TBK_PARAM': params.return_value
            },
            headers={
                'User-Agent': user_agent
            }
        )
        commerce.webpay_decrypt.assert_called_once_with(response.content)

        self.assertEqual(token, 'aA123')

    @mock.patch('tbk.webpay.payment.requests')
    @mock.patch('tbk.webpay.payment.Payment.process_url')
    @mock.patch('tbk.webpay.payment.Payment.params')
    def test_fetch_token_not_ok(self, params, process_url, requests):
        """
        payment.fetch_token must post data to process_url and fail when status_code is not 200
        """
        payment = Payment(**self.payment_kwargs)
        response = requests.post.return_value
        response.status_code = 500

        self.assertRaisesRegexp(
            PaymentError, "Payment token generation failed",
            payment.fetch_token
        )

    @mock.patch('tbk.webpay.payment.requests')
    @mock.patch('tbk.webpay.payment.Payment.process_url')
    @mock.patch('tbk.webpay.payment.Payment.params')
    def test_fetch_token_with_error(self, params, process_url, requests):
        """
        payment.fetch_token must post data to process_url and fail with ERROR code
        """
        payment = Payment(**self.payment_kwargs)
        response = requests.post.return_value
        response.status_code = 200
        commerce = self.payment_kwargs['commerce']
        decrypted = {'body': 'TOKEN=aA123,ERROR=aA321'}
        commerce.webpay_decrypt.return_value = decrypted

        self.assertRaisesRegexp(
            PaymentError, "Payment token generation failed. ERROR=aA321",
            payment.fetch_token
        )

    def test_validation_url_production(self):
        """
        payment.validation_url on prod. must returns
        https://webpay.transbank.cl:443/filtroUnificado/bp_validacion.cgi
        """
        commerce = mock.Mock()
        commerce.testing = False
        self.payment_kwargs['commerce'] = commerce
        payment = Payment(**self.payment_kwargs)

        self.assertEqual(
            "https://webpay.transbank.cl:443/filtroUnificado/bp_validacion.cgi",
            payment.validation_url()
        )

    def test_validation_url_development(self):
        """
        payment.validation_url on dev. must returns
        https://certificacion.webpay.cl:6443/filtroUnificado/bp_validacion.cgi
        """
        commerce = mock.Mock()
        commerce.testing = True
        self.payment_kwargs['commerce'] = commerce
        payment = Payment(**self.payment_kwargs)

        self.assertEqual(
            "https://certificacion.webpay.cl:6443/filtroUnificado/bp_validacion.cgi",
            payment.validation_url()
        )

    @mock.patch('tbk.webpay.payment.Payment.raw_params')
    @mock.patch('tbk.webpay.payment.Payment.verify')
    def test_params_not_created(self, verify, raw_params):
        """
        payment.params must verify and returns encrypted raw_params
        """
        commerce = self.payment_kwargs['commerce']
        payment = Payment(**self.payment_kwargs)

        result = payment.params()

        verify.assert_called_once_with()
        commerce.webpay_encrypt.assert_called_once_with(raw_params.return_value)
        self.assertEqual(result, commerce.webpay_encrypt.return_value)
        raw_params.assert_called_once_with()

    @mock.patch('tbk.webpay.payment.Payment.raw_params')
    @mock.patch('tbk.webpay.payment.Payment.verify')
    def test_params_created(self, verify, raw_params):
        """
        payment.params must returns the already verified and encrypted raw_params
        """
        commerce = self.payment_kwargs['commerce']
        payment = Payment(**self.payment_kwargs)
        result = payment.params()

        verify.reset_mock()
        commerce.webpay_encrypt.reset_mock()
        raw_params.reset_mock()

        self.assertEqual(payment.params(), result)
        self.assertFalse(verify.called)
        self.assertFalse(commerce.webpay_encrypt.called)
        self.assertFalse(raw_params.called)

    @mock.patch('tbk.webpay.payment.Payment.raw_params')
    @mock.patch('tbk.webpay.payment.Payment.verify')
    def test_params_doesnt_verify(self, verify, raw_params):
        """
        payment.params must fail with PaymentError when verify fail
        """
        payment = Payment(**self.payment_kwargs)
        verify.side_effect = PaymentError

        self.assertRaises(PaymentError, payment.params)
        verify.assert_called_once_with()