"""Verificações de integração da aplicação após a troca de banco.

O runner do Django cria e remove um banco de testes independente.
"""

from datetime import timedelta

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.models import User
from coordenador.models import Coordenador
from medicos.models import Medico
from pacientes.models import Paciente

from .models import (
    AgendamentoExame,
    Consulta,
    Exame,
    HorarioDisponivel,
    HorarioExameDisponivel,
)


class PostgreSQLIntegrationTests(TestCase):
    def force_mfa_login(self, user):
        """Os testes de negócio começam com uma sessão já verificada."""
        self.client.force_login(user)
        device, _ = TOTPDevice.objects.get_or_create(user=user, name='integration', confirmed=True)
        session = self.client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()

    @classmethod
    def setUpTestData(cls):
        cls.patient_user = User.objects.create_user(
            username='patient_test', password='test-only-password', tipo='PACIENTE'
        )
        cls.patient = Paciente.objects.create(usuario=cls.patient_user)
        cls.doctor_user = User.objects.create_user(
            username='doctor_test', password='test-only-password', tipo='MEDICO'
        )
        cls.doctor = Medico.objects.create(
            usuario=cls.doctor_user, crm='TEST-001', especialidade='Clínica'
        )
        cls.coordinator_user = User.objects.create_user(
            username='coordinator_test', password='test-only-password', tipo='COORDENADOR'
        )
        cls.coordinator = Coordenador.objects.create(
            usuario=cls.coordinator_user, matricula='TEST-001'
        )
        cls.exam = Exame.objects.create(nome='Exame de teste')
        cls.time = timezone.now() + timedelta(days=7)

    def test_real_postgresql_connection(self):
        self.assertEqual(connection.vendor, 'postgresql')
        with connection.cursor() as cursor:
            cursor.execute('SELECT version()')
            self.assertIn('PostgreSQL', cursor.fetchone()[0])

    def test_public_pages(self):
        for url in ('/', '/conta/paciente/login/', '/conta/medico/login/', '/admin/login/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_patient_registration_and_login(self):
        response = self.client.post(reverse('accounts:registrar_paciente'), {
            'username': 'registered_test', 'first_name': 'Paciente', 'last_name': 'Teste',
            'email': 'patient@example.com', 'telefone': '41999999999',
            'data_nascimento': '1990-01-01',
            'password1': 'Registration-test-123!', 'password2': 'Registration-test-123!',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='registered_test')
        self.assertTrue(Paciente.objects.filter(usuario=user).exists())
        self.client.logout()
        response = self.client.post(reverse('accounts:login_paciente'), {
            'username': user.username, 'password': 'Registration-test-123!',
        })
        self.assertRedirects(response, reverse('accounts:mfa_setup'))

    def test_role_pages_and_calendars(self):
        profiles = (
            (self.patient_user, ('pacientes:dashboard', 'pacientes:consultas', 'pacientes:exames')),
            (self.doctor_user, ('medicos:dashboard', 'medicos:disponibilidade', 'medicos:consultas_calendario')),
            (self.coordinator_user, ('coordenador:dashboard', 'coordenador:disponibilidade', 'coordenador:exames_calendario')),
        )
        for user, routes in profiles:
            self.force_mfa_login(user)
            for route in routes:
                with self.subTest(route=route):
                    self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_professional_login_and_admin(self):
        for user, route in (
            (self.doctor_user, 'medicos:dashboard'),
            (self.coordinator_user, 'coordenador:dashboard'),
        ):
            self.client.logout()
            response = self.client.post(reverse('accounts:login_medico'), {
                'username': user.username, 'password': 'test-only-password',
            })
            self.assertRedirects(response, reverse('accounts:mfa_setup'))
        admin = User.objects.create_superuser(
            username='admin_test', password='test-only-password', email='admin@example.com'
        )
        self.force_mfa_login(admin)
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        self.assertEqual(self.client.get('/admin/consultas/exame/').status_code, 200)

    def test_consultation_booking_and_cancellation(self):
        slot = HorarioDisponivel.objects.create(medico=self.doctor, data_hora=self.time)
        self.force_mfa_login(self.patient_user)
        availability = self.client.get(reverse('pacientes:horarios_disponiveis', args=[self.doctor.pk]))
        self.assertEqual(availability.json()['eventos'][0]['id'], slot.pk)
        response = self.client.post(reverse('pacientes:agendar_consulta', args=[slot.pk]))
        self.assertRedirects(response, reverse('pacientes:consultas'))
        booking = Consulta.objects.get(paciente=self.patient)
        slot.refresh_from_db()
        self.assertFalse(slot.ativo)
        self.assertEqual(booking.data_hora, self.time)
        response = self.client.post(reverse('pacientes:cancelar_consulta', args=[booking.pk]))
        self.assertRedirects(response, reverse('pacientes:consultas'))
        slot.refresh_from_db()
        self.assertTrue(slot.ativo)
        self.assertFalse(Consulta.objects.exists())

    def test_exam_booking_and_cancellation(self):
        slot = HorarioExameDisponivel.objects.create(
            exame=self.exam, medico_responsavel=self.doctor,
            coordenador=self.coordinator, data_hora=self.time,
        )
        self.force_mfa_login(self.patient_user)
        response = self.client.post(reverse('pacientes:agendar_exame', args=[slot.pk]))
        self.assertRedirects(response, reverse('pacientes:exames'))
        booking = AgendamentoExame.objects.get(paciente=self.patient)
        self.assertEqual(booking.medico_responsavel, self.doctor)
        slot.refresh_from_db()
        self.assertFalse(slot.ativo)
        response = self.client.post(reverse('pacientes:cancelar_exame', args=[booking.pk]))
        self.assertRedirects(response, reverse('pacientes:exames'))
        slot.refresh_from_db()
        self.assertTrue(slot.ativo)
        self.assertFalse(AgendamentoExame.objects.exists())

    def test_exam_conflict_blocks_consultation(self):
        slot = HorarioDisponivel.objects.create(medico=self.doctor, data_hora=self.time)
        HorarioExameDisponivel.objects.create(
            exame=self.exam, medico_responsavel=self.doctor,
            coordenador=self.coordinator, data_hora=self.time,
        )
        self.force_mfa_login(self.patient_user)
        response = self.client.post(reverse('pacientes:agendar_consulta', args=[slot.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Consulta.objects.exists())

    def test_consultation_conflict_blocks_exam(self):
        slot = HorarioExameDisponivel.objects.create(
            exame=self.exam, medico_responsavel=self.doctor,
            coordenador=self.coordinator, data_hora=self.time,
        )
        Consulta.objects.create(medico=self.doctor, paciente=self.patient, data_hora=self.time)
        self.force_mfa_login(self.patient_user)
        response = self.client.post(reverse('pacientes:agendar_exame', args=[slot.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AgendamentoExame.objects.exists())

    def test_optional_exam_relations_are_validated(self):
        self.force_mfa_login(self.patient_user)
        for doctor, coordinator, offset in (
            (None, self.coordinator, 1),
            (self.doctor, None, 2),
        ):
            with self.subTest(doctor=doctor, coordinator=coordinator):
                slot = HorarioExameDisponivel.objects.create(
                    exame=self.exam, medico_responsavel=doctor, coordenador=coordinator,
                    data_hora=self.time + timedelta(hours=offset),
                )
                response = self.client.post(reverse('pacientes:agendar_exame', args=[slot.pk]))
                self.assertEqual(response.status_code, 403)
                slot.refresh_from_db()
                self.assertTrue(slot.ativo)
        self.assertFalse(AgendamentoExame.objects.exists())

    def test_database_rejects_duplicate_consultation(self):
        Consulta.objects.create(medico=self.doctor, paciente=self.patient, data_hora=self.time)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Consulta.objects.create(medico=self.doctor, paciente=self.patient, data_hora=self.time)

    def test_database_rejects_duplicate_exam(self):
        values = dict(
            exame=self.exam, paciente=self.patient,
            medico_responsavel=self.doctor, data_hora=self.time,
        )
        AgendamentoExame.objects.create(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AgendamentoExame.objects.create(**values)
