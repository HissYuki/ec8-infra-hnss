import re
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth.hashers import check_password
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from consultas import test_postgresql as integration_tests
from .models import PatientPasswordResetCode, User
from . import tests as authentication_tests


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PASSWORD_RESET_TIMEOUT=600)
class PasswordRecoveryTests(TestCase):
    password = authentication_tests.AuthenticationTests.password
    force_mfa_login = integration_tests.PostgreSQLIntegrationTests.force_mfa_login

    @classmethod
    def setUpTestData(cls):
        authentication_tests.AuthenticationTests.setUpTestData.__func__(cls)

    def request_code(self, email=None):
        response = self.client.post(reverse('accounts:password_reset'), {
            'email': email or self.users['PACIENTE'].email,
        })
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        return re.search(r'é: ([0-9]{6})', mail.outbox[-1].body).group(1)

    def verify_code(self, code):
        return self.client.post(reverse('accounts:password_reset_done'), {'code': code})

    def save_password(self, password='Replacement-test-password-456!'):
        return self.client.post(reverse('accounts:password_reset_confirm'), {
            'new_password1': password, 'new_password2': password,
        })

    def test_codigo_email_hash_e_confirmacao_generica(self):
        code = self.request_code()
        self.assertEqual(mail.outbox[0].to, [self.users['PACIENTE'].email])
        self.assertEqual(len(code), 6)
        challenge = PatientPasswordResetCode.objects.get()
        self.assertNotEqual(challenge.code_hash, code)
        self.assertTrue(check_password(code, challenge.code_hash))
        self.assertAlmostEqual((challenge.expires_at - challenge.last_sent_at).total_seconds(), 600)
        self.assertContains(self.client.get(reverse('accounts:password_reset_done')), 'Se existir uma conta de paciente')

    def test_codigo_correto_altera_senha_uma_vez_e_preserva_mfa(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        device = TOTPDevice.objects.create(user=self.users['PACIENTE'], name='existing', confirmed=True)
        code = self.request_code()
        identifier = self.client.session['reset_code_id']
        self.assertRedirects(self.verify_code(code), reverse('accounts:password_reset_confirm'))
        self.assertRedirects(self.save_password(), reverse('accounts:password_reset_complete'))
        user = User.objects.get(pk=self.users['PACIENTE'].pk)
        self.assertTrue(user.check_password('Replacement-test-password-456!'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(TOTPDevice.objects.filter(pk=device.pk).exists())
        self.assertIsNotNone(PatientPasswordResetCode.objects.get().used_at)
        session = self.client.session
        session['reset_code_id'] = identifier
        session['reset_verified_id'] = identifier
        session.save()
        self.assertContains(self.verify_code(code), 'Código inválido')
        self.assertRedirects(self.save_password(), reverse('accounts:password_reset_done'))
        self.assertRedirects(self.client.post(reverse('accounts:login_paciente'), {
            'username': user.username, 'password': 'Replacement-test-password-456!',
        }), reverse('accounts:mfa_verify'))

    def test_codigo_incorreto_limite_persistente_entre_sessoes(self):
        code = self.request_code()
        wrong = '000000' if code != '000000' else '000001'
        identifier = self.client.session['reset_code_id']
        for _ in range(5):
            self.assertContains(self.verify_code(wrong), 'Código inválido')
        self.assertEqual(PatientPasswordResetCode.objects.get().attempts, 5)
        self.client = Client()
        session = self.client.session
        session['reset_code_id'] = identifier
        session.save()
        self.assertContains(self.verify_code(code), 'Código inválido')

    def test_codigo_expirado_e_autorizacao_expirada(self):
        code = self.request_code()
        challenge = PatientPasswordResetCode.objects.get()
        challenge.expires_at = timezone.now() - timedelta(seconds=1)
        challenge.save()
        self.assertContains(self.verify_code(code), 'Código inválido')
        challenge.expires_at = timezone.now() + timedelta(minutes=1)
        challenge.save()
        self.assertRedirects(self.verify_code(code), reverse('accounts:password_reset_confirm'))
        challenge.refresh_from_db()
        challenge.expires_at = timezone.now() - timedelta(seconds=1)
        challenge.save()
        self.assertRedirects(self.save_password(), reverse('accounts:password_reset_done'))

    def test_nao_pacientes_inexistentes_inativos_e_staff_silenciosos(self):
        user = self.users['PACIENTE']
        user.is_staff = True
        user.save()
        for email in [u.email for u in self.users.values()] + ['missing@example.com']:
            response = self.client.post(reverse('accounts:password_reset'), {'email': email})
            self.assertRedirects(response, reverse('accounts:password_reset_done'))
            self.assertContains(self.client.get(response.url), 'enviaremos um código de recuperação')
            self.assertEqual(len(mail.outbox), 0)
        user.is_staff = False
        user.is_active = False
        user.save()
        self.client.post(reverse('accounts:password_reset'), {'email': user.email})
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(PatientPasswordResetCode.objects.exists())

    def test_codigo_nao_autoriza_outro_usuario_ou_sessao(self):
        code = self.request_code()
        other = Client()
        self.assertContains(other.post(reverse('accounts:password_reset_done'), {'code': code}), 'Código inválido')
        self.assertRedirects(other.post(reverse('accounts:password_reset_confirm'), {
            'new_password1': 'Another-password-123!', 'new_password2': 'Another-password-123!',
        }), reverse('accounts:password_reset_done'))
        self.assertRedirects(self.save_password(), reverse('accounts:password_reset_done'))

    def test_email_atualizado_em_meus_dados_e_invalida_codigo_antigo(self):
        original = self.users['PACIENTE'].email
        code = self.request_code()
        identifier = self.client.session['reset_code_id']
        self.force_mfa_login(self.users['PACIENTE'])
        response = self.client.post(reverse('pacientes:meus_dados'), {
            'first_name': 'Paciente', 'last_name': 'Novo', 'email': 'novo@example.com',
            'telefone': '123', 'data_nascimento': '1990-01-01',
        }, follow=True)
        self.assertContains(response, 'Informações atualizadas com sucesso.')
        self.client.logout()
        session = self.client.session
        session['reset_code_id'] = identifier
        session.save()
        self.assertContains(self.verify_code(code), 'Código inválido')
        mail.outbox.clear()
        self.client.post(reverse('accounts:password_reset'), {'email': original})
        self.assertEqual(len(mail.outbox), 0)
        with override_settings(PASSWORD_RESET_RESEND_INTERVAL=0):
            self.request_code('novo@example.com')
        self.assertEqual(mail.outbox[0].to, ['novo@example.com'])

    def test_reenvio_limitado_e_novo_codigo_invalida_anterior(self):
        code = self.request_code()
        identifier = self.client.session['reset_code_id']
        self.client.post(reverse('accounts:password_reset'), {'email': self.users['PACIENTE'].email})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.session['reset_code_id'], identifier)
        with override_settings(PASSWORD_RESET_RESEND_INTERVAL=0):
            self.request_code()
        self.assertEqual(len(mail.outbox), 2)
        self.assertFalse(PatientPasswordResetCode.objects.filter(pk=identifier).exists())

    def test_paciente_promovido_nao_pode_redefinir(self):
        code = self.request_code()
        self.assertRedirects(self.verify_code(code), reverse('accounts:password_reset_confirm'))
        User.objects.filter(pk=self.users['PACIENTE'].pk).update(tipo='MEDICO')
        self.assertRedirects(self.save_password(), reverse('accounts:password_reset_done'))

    def test_validadores_de_senha_e_codigo_nao_reutilizavel(self):
        code = self.request_code()
        self.verify_code(code)
        self.assertContains(self.save_password('123'), 'errorlist')
        self.assertContains(self.verify_code(code), 'Código inválido')
        self.assertIsNone(PatientPasswordResetCode.objects.get().used_at)
        self.assertRedirects(self.save_password(), reverse('accounts:password_reset_complete'))

    def test_falha_smtp_nao_enumera_contas(self):
        with patch('accounts.password_recovery.send_mail', side_effect=SMTPException('falha')):
            with self.assertLogs('accounts.password_recovery', level='ERROR'):
                response = self.client.post(reverse('accounts:password_reset'), {'email': self.users['PACIENTE'].email})
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertContains(self.client.get(response.url), 'Se existir uma conta de paciente')
        self.assertLessEqual(PatientPasswordResetCode.objects.get().expires_at, timezone.now())

    def test_endereco_ambiguo_nao_recupera_conta_arbitraria(self):
        User.objects.create_user(username='duplicate', email=self.users['PACIENTE'].email, tipo='PACIENTE', password='Another-password-123!')
        self.client.post(reverse('accounts:password_reset'), {'email': self.users['PACIENTE'].email})
        self.assertEqual(len(mail.outbox), 0)

    def test_csrf_em_todas_as_etapas(self):
        secure = Client(enforce_csrf_checks=True)
        for route in ('accounts:password_reset', 'accounts:password_reset_done', 'accounts:password_reset_confirm'):
            self.assertEqual(secure.post(reverse(route), {}).status_code, 403)

    def test_codigo_com_zero_inicial(self):
        with patch('accounts.password_recovery.secrets.randbelow', return_value=1234):
            code = self.request_code()
        self.assertEqual(code, '001234')
        self.assertRedirects(self.verify_code(code), reverse('accounts:password_reset_confirm'))
