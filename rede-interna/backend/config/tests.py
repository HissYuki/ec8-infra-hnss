from django.test import Client, SimpleTestCase, override_settings


@override_settings(
    ALLOWED_HOSTS=['hospital.example'],
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
)
class ProxySettingsTests(SimpleTestCase):
    def test_https_forwarding_has_no_redirect_loop(self):
        response = self.client.get('/', HTTP_HOST='hospital.example', HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code, 200)

    def test_plain_http_redirects_to_https(self):
        response = self.client.get('/', HTTP_HOST='hospital.example')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://hospital.example/')

    def test_invalid_host_is_rejected(self):
        response = self.client.get('/', HTTP_HOST='other.example', HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code, 400)

    def test_login_csrf_cookie_is_secure(self):
        response = self.client.get('/conta/paciente/login/', HTTP_HOST='hospital.example', secure=True)
        self.assertTrue(response.cookies['csrftoken']['secure'])

    def test_https_form_rejects_foreign_origin(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get('/conta/paciente/login/', HTTP_HOST='hospital.example', secure=True)
        response = client.post('/conta/paciente/login/',
            {'csrfmiddlewaretoken': response.cookies['csrftoken'].value},
            HTTP_HOST='hospital.example', secure=True, HTTP_ORIGIN='https://other.example')
        self.assertEqual(response.status_code, 403)
