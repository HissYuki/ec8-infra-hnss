from django.contrib import admin
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from coordenador.models import Coordenador
from medicos.models import Medico
from pacientes.models import Paciente

from .models import User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AuthenticationTests(TestCase):
    password = 'Initial-test-password-123!'

    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in ('PACIENTE', 'MEDICO', 'COORDENADOR'):
            cls.users[role] = User.objects.create_user(
                username=role.lower(), email=f'{role.lower()}@example.com',
                password=cls.password, tipo=role,
            )
        cls.users['ADMIN'] = User.objects.create_superuser(
            username='admin', email='admin@example.com', password=cls.password,
        )
        Paciente.objects.create(usuario=cls.users['PACIENTE'])
        Medico.objects.create(usuario=cls.users['MEDICO'], crm='AUTH-001', especialidade='Clínica')
        Coordenador.objects.create(usuario=cls.users['COORDENADOR'], matricula='AUTH-001')

    def login(self, role, next_url=None, password=None):
        route = ('admin:login' if role == 'ADMIN' else
                 'accounts:login_paciente' if role == 'PACIENTE' else 'accounts:login_medico')
        data = {'username': self.users[role].username, 'password': password or self.password}
        if next_url:
            data['next'] = next_url
        return self.client.post(reverse(route), data)

    def device(self, role='PACIENTE', confirmed=True):
        return TOTPDevice.objects.create(user=self.users[role], name='hospital', confirmed=confirmed)

    def token(self, device):
        return str(totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits)).zfill(6)

    def enroll(self, role='PACIENTE'):
        self.login(role)
        self.client.get(reverse('accounts:mfa_setup'))
        device = TOTPDevice.objects.get(user=self.users[role], confirmed=False)
        response = self.client.post(reverse('accounts:mfa_setup'), {'token': self.token(device)})
        self.assertContains(response, 'MFA ativado')
        return TOTPDevice.objects.get(pk=device.pk), response

    def assert_login_mfa(self, role):
        device = self.device(role)
        response = self.login(role)
        self.assertRedirects(response, reverse('accounts:mfa_verify'))
        response = self.client.post(reverse('accounts:mfa_verify'), {'token': self.token(device)})
        route = {'PACIENTE': 'pacientes:dashboard', 'MEDICO': 'medicos:dashboard',
                 'COORDENADOR': 'coordenador:dashboard', 'ADMIN': 'admin:index'}[role]
        self.assertRedirects(response, reverse(route))

    def test_patient_login(self):
        self.assert_login_mfa('PACIENTE')

    def test_doctor_login(self):
        self.assert_login_mfa('MEDICO')

    def test_coordinator_login(self):
        self.assert_login_mfa('COORDENADOR')

    def test_admin_login(self):
        self.assert_login_mfa('ADMIN')

    def test_all_roles_must_enroll(self):
        for role in self.users:
            with self.subTest(role=role):
                self.client.logout()
                self.assertRedirects(self.login(role), reverse('accounts:mfa_setup'))

    def test_invalid_password_does_not_start_session(self):
        for role in self.users:
            with self.subTest(role=role):
                response = self.login(role, password='incorrect')
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_pages_reject_wrong_roles(self):
        for role in ('MEDICO', 'COORDENADOR', 'ADMIN'):
            response = self.client.post(reverse('accounts:login_paciente'), {
                'username': self.users[role].username, 'password': self.password,
            })
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('accounts:login_medico'), {
            'username': self.users['PACIENTE'].username, 'password': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_initial_enrollment_activates_only_after_valid_token(self):
        self.login('PACIENTE')
        self.client.get(reverse('accounts:mfa_setup'))
        self.assertFalse(TOTPDevice.objects.get(user=self.users['PACIENTE']).confirmed)
        response = self.client.post(reverse('accounts:mfa_setup'), {'token': 'invalid'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.get(user=self.users['PACIENTE']).confirmed)
        device = TOTPDevice.objects.get(user=self.users['PACIENTE'])
        response = self.client.post(reverse('accounts:mfa_setup'), {'token': self.token(device)})
        self.assertEqual(len(response.context['codes']), 10)
        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        self.assertEqual(self.client.session[DEVICE_ID_SESSION_KEY], device.persistent_id)
        self.assertRedirects(self.client.get(reverse('accounts:mfa_finish')), reverse('pacientes:dashboard'))

    def test_qr_is_local_authenticated_and_uncached(self):
        self.assertEqual(self.client.get(reverse('accounts:mfa_qr')).status_code, 302)
        self.login('PACIENTE')
        response = self.client.get(reverse('accounts:mfa_qr'))
        self.assertEqual(response['Content-Type'], 'image/svg+xml')
        self.assertIn(b'<svg', response.content)
        self.assertIn('no-store', response['Cache-Control'])

    def test_codes_are_not_redisplayed(self):
        _, response = self.enroll()
        code = response.context['codes'][0]
        response = self.client.get(reverse('accounts:mfa_setup'), follow=True)
        self.assertNotContains(response, code)

    def test_invalid_mfa_and_throttling(self):
        device = self.device()
        self.login('PACIENTE')
        current = int(self.token(device))
        invalid = str((current + 12345) % 1000000).zfill(6)
        response = self.client.post(reverse('accounts:mfa_verify'), {'token': invalid})
        self.assertContains(response, 'Código inválido')
        self.assertNotIn(DEVICE_ID_SESSION_KEY, self.client.session)
        device.refresh_from_db()
        self.assertGreater(device.throttling_failure_count, 0)
        response = self.client.post(reverse('accounts:mfa_verify'), {'token': self.token(device)})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(DEVICE_ID_SESSION_KEY, self.client.session)

    def test_totp_replay_is_rejected(self):
        device = self.device()
        self.login('PACIENTE')
        code = self.token(device)
        self.client.post(reverse('accounts:mfa_verify'), {'token': code})
        self.client.logout()
        self.login('PACIENTE')
        response = self.client.post(reverse('accounts:mfa_verify'), {'token': code})
        self.assertContains(response, 'Código inválido')
        self.assertNotIn(DEVICE_ID_SESSION_KEY, self.client.session)

    def test_unverified_users_cannot_access_any_role_or_admin(self):
        routes = ('pacientes:dashboard', 'medicos:dashboard', 'coordenador:dashboard', 'admin:index')
        for role in self.users:
            self.client.logout()
            self.login(role)
            for route in routes:
                with self.subTest(role=role, route=route):
                    self.assertRedirects(self.client.get(reverse(route)), reverse('accounts:mfa_setup'))
            self.assertEqual(self.client.post('/admin/accounts/user/add/').status_code, 302)

    def test_admin_site_itself_requires_verified_user(self):
        request = RequestFactory().get(reverse('admin:index'))
        request.user = self.users['ADMIN']
        request.session = {}
        self.assertFalse(admin.site.has_permission(request))

    def test_password_only_cannot_replace_existing_mfa_or_read_qr(self):
        device = self.device()
        self.login('PACIENTE')
        self.assertRedirects(self.client.get(reverse('accounts:mfa_setup')), reverse('accounts:mfa_verify'))
        self.assertEqual(self.client.get(reverse('accounts:mfa_qr')).status_code, 404)
        self.assertRedirects(self.client.post(reverse('accounts:mfa_setup'), {'token': self.token(device)}), reverse('accounts:mfa_verify'))
        self.assertEqual(TOTPDevice.objects.filter(user=self.users['PACIENTE']).count(), 1)

    def test_pending_session_expires(self):
        self.login('PACIENTE')
        session = self.client.session
        session['mfa_started_at'] = 0
        session.save()
        response = self.client.get(reverse('accounts:mfa_setup'))
        self.assertRedirects(response, reverse('accounts:login_paciente'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_preexisting_password_session_is_not_grandfathered(self):
        self.client.force_login(self.users['ADMIN'])
        self.assertRedirects(self.client.get(reverse('admin:index')), reverse('admin:login'))

    def test_recovery_code_consumed_once_and_requires_reenrollment(self):
        previous, _ = self.enroll()
        static = StaticDevice.objects.get(user=self.users['PACIENTE'])
        code = static.token_set.first().token
        self.client.logout()
        self.login('PACIENTE')
        response = self.client.post(reverse('accounts:mfa_recover'), {'token': code[:4] + '-' + code[4:]})
        self.assertRedirects(response, reverse('accounts:mfa_setup'))
        self.assertFalse(StaticToken.objects.filter(device=static, token=code).exists())
        self.assertRedirects(self.client.get(reverse('pacientes:dashboard')), reverse('accounts:mfa_setup'))
        self.client.logout()
        self.login('PACIENTE')
        response = self.client.post(reverse('accounts:mfa_recover'), {'token': code})
        self.assertContains(response, 'Código inválido')
        self.assertNotIn(DEVICE_ID_SESSION_KEY, self.client.session)
        # Outro código válido permite concluir a troca e invalida os códigos antigos.
        static.refresh_from_db()
        static.throttle_reset()
        code2 = static.token_set.first().token
        self.client.post(reverse('accounts:mfa_recover'), {'token': code2})
        self.client.get(reverse('accounts:mfa_setup'))
        new_device = TOTPDevice.objects.get(user=self.users['PACIENTE'], confirmed=False)
        response = self.client.post(reverse('accounts:mfa_setup'), {'token': self.token(new_device)})
        self.assertContains(response, 'MFA ativado')
        self.assertFalse(TOTPDevice.objects.filter(pk=previous.pk).exists())
        self.assertEqual(static.token_set.count(), 10)
        self.assertRedirects(self.client.get(reverse('accounts:mfa_finish')), reverse('pacientes:dashboard'))

    def test_recovery_codes_require_password_first(self):
        response = self.client.post(reverse('accounts:mfa_recover'), {'token': 'ABCD-EFGH'})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(DEVICE_ID_SESSION_KEY, self.client.session)

    def test_safe_next_and_open_redirect(self):
        device = self.device()
        self.login('PACIENTE', next_url='https://attacker.example/')
        response = self.client.post(reverse('accounts:mfa_verify'), {'token': self.token(device)})
        self.assertRedirects(response, reverse('pacientes:dashboard'))

    def test_internal_next_after_mfa(self):
        device = self.device()
        self.login('PACIENTE', next_url=reverse('pacientes:consultas'))
        response = self.client.post(reverse('accounts:mfa_verify'), {'token': self.token(device)})
        self.assertRedirects(response, reverse('pacientes:consultas'))

    def test_anonymous_redirects_by_area(self):
        for route, login in (('pacientes:dashboard', 'accounts:login_paciente'),
                             ('medicos:dashboard', 'accounts:login_medico'),
                             ('coordenador:dashboard', 'accounts:login_medico'),
                             ('admin:index', 'admin:login')):
            response = self.client.get(reverse(route))
            self.assertTrue(response.url.startswith(reverse(login) + '?next='))

    def test_logout_redirects_all_roles(self):
        for role, login in (('PACIENTE', 'accounts:login_paciente'), ('MEDICO', 'accounts:login_medico'),
                            ('COORDENADOR', 'accounts:login_medico'), ('ADMIN', 'admin:login')):
            with self.subTest(role=role):
                self.login(role)
                response = self.client.post(reverse('accounts:logout'))
                self.assertRedirects(response, reverse(login))
                self.assertNotIn('_auth_user_id', self.client.session)

    def test_admin_native_logout_redirects_to_login_even_pending_mfa(self):
        self.login('ADMIN')
        response = self.client.post(reverse('admin:logout'))
        self.assertRedirects(response, reverse('admin:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_verified_admin_native_logout_redirects_to_admin_login(self):
        self.assert_login_mfa('ADMIN')
        response = self.client.post(reverse('admin:logout'))
        self.assertRedirects(response, reverse('admin:login'))
        self.assertNotIn(DEVICE_ID_SESSION_KEY, self.client.session)

    def test_admin_internal_next_is_preserved_after_mfa(self):
        device = self.device('ADMIN')
        destination = reverse('admin:accounts_user_changelist')
        self.login('ADMIN', next_url=destination)
        response = self.client.post(reverse('accounts:mfa_verify'), {'token': self.token(device)})
        self.assertRedirects(response, destination)

    def test_mfa_forms_require_csrf(self):
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.users['PACIENTE'])
        session = secure_client.session
        import time
        session['mfa_started_at'] = time.time()
        session.save()
        for route in ('accounts:mfa_setup', 'accounts:mfa_verify', 'accounts:mfa_recover'):
            self.assertEqual(secure_client.post(reverse(route), {'token': '123456'}).status_code, 403)

    def test_logout_is_post_only_and_csrf_protected(self):
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
        self.assertEqual(self.client.get(reverse('admin:logout')).status_code, 405)
        secure_client = Client(enforce_csrf_checks=True)
        self.assertEqual(secure_client.post(reverse('admin:logout')).status_code, 403)
        self.assertEqual(secure_client.post(reverse('accounts:logout')).status_code, 403)
