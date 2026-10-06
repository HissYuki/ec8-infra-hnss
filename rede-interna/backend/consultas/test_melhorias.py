from datetime import timedelta
from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from medicos.models import Medico
from .models import AgendamentoExame, Consulta, Exame, HorarioDisponivel, HorarioExameDisponivel
from . import test_postgresql as integration_tests


class MelhoriasFuncionaisTests(TestCase):
    force_mfa_login = integration_tests.PostgreSQLIntegrationTests.force_mfa_login

    @classmethod
    def setUpTestData(cls):
        integration_tests.PostgreSQLIntegrationTests.setUpTestData.__func__(cls)

    def test_disponibilidade_substituida_por_consulta_sem_duplicacao(self):
        slot = HorarioDisponivel.objects.create(medico=self.doctor, data_hora=self.time)
        self.force_mfa_login(self.doctor_user)
        url = reverse('medicos:consultas_calendario')
        eventos = self.client.get(url).json()
        self.assertEqual([e['id'] for e in eventos], [f'disponivel-{slot.pk}'])
        self.force_mfa_login(self.patient_user)
        self.client.post(reverse('pacientes:agendar_consulta', args=[slot.pk]))
        consulta = Consulta.objects.get(paciente=self.patient)
        self.force_mfa_login(self.doctor_user)
        eventos = self.client.get(url).json()
        self.assertEqual([e['id'] for e in eventos], [f'consulta-{consulta.pk}'])
        self.assertEqual(eventos[0]['url'], reverse('medicos:detalhe_consulta', args=[consulta.pk]))
        self.force_mfa_login(self.patient_user)
        self.client.post(reverse('pacientes:cancelar_consulta', args=[consulta.pk]))
        self.force_mfa_login(self.doctor_user)
        self.assertEqual(self.client.get(url).json()[0]['id'], f'disponivel-{slot.pk}')

    def test_exame_reservado_e_agendado_sem_disponibilidade_duplicada(self):
        HorarioDisponivel.objects.create(medico=self.doctor, data_hora=self.time)
        horario = HorarioExameDisponivel.objects.create(
            exame=self.exam, medico_responsavel=self.doctor, coordenador=self.coordinator, data_hora=self.time,
        )
        self.force_mfa_login(self.doctor_user)
        url = reverse('medicos:consultas_calendario')
        eventos = self.client.get(url).json()
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]['id'], f'exame-{horario.pk}')
        self.assertIn('Disponível', eventos[0]['title'])
        AgendamentoExame.objects.create(
            exame=self.exam, paciente=self.patient, medico_responsavel=self.doctor,
            coordenador=self.coordinator, data_hora=self.time,
        )
        eventos = self.client.get(url).json()
        self.assertEqual(len(eventos), 1)
        self.assertIn(self.patient_user.username, eventos[0]['title'])
        self.force_mfa_login(self.coordinator_user)
        self.assertIn('evento-exame-agendado', self.client.get(reverse('coordenador:exames_calendario')).json()[0]['classNames'])

    def test_consulta_detalhes_anotacoes_historico_e_acesso(self):
        consulta = Consulta.objects.create(medico=self.doctor, paciente=self.patient, data_hora=self.time)
        anterior = Consulta.objects.create(
            medico=self.doctor, paciente=self.patient, data_hora=timezone.now() - timedelta(days=30),
            observacoes='Histórico autorizado',
        )
        self.force_mfa_login(self.doctor_user)
        url = reverse('medicos:detalhe_consulta', args=[consulta.pk])
        self.assertContains(self.client.get(url), 'Histórico autorizado')
        response = self.client.post(url, {'observacoes': '<script>nota</script>'}, follow=True)
        self.assertContains(response, 'Observações da consulta salvas com sucesso.')
        consulta.refresh_from_db()
        self.assertEqual(consulta.observacoes, '<script>nota</script>')
        self.assertContains(self.client.get(url), '&lt;script&gt;nota&lt;/script&gt;')
        outro_user = User.objects.create_user(username='outro_medico', tipo='MEDICO')
        outro = Medico.objects.create(usuario=outro_user, crm='OTHER-001', especialidade='Clínica')
        Consulta.objects.create(medico=outro, paciente=self.patient, data_hora=timezone.now(), observacoes='Nota de outro médico')
        self.assertNotContains(self.client.get(url), 'Nota de outro médico')
        self.force_mfa_login(outro_user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'observacoes': 'Alteração proibida'}).status_code, 404)
        consulta.refresh_from_db()
        self.assertEqual(consulta.observacoes, '<script>nota</script>')
        self.force_mfa_login(self.patient_user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotContains(self.client.get(reverse('pacientes:consultas')), 'Histórico autorizado')

    def test_meus_dados_sucesso_e_erros(self):
        self.force_mfa_login(self.patient_user)
        url = reverse('pacientes:meus_dados')
        values = dict(first_name='Novo', last_name='Nome', email='novo@example.com', telefone='123', data_nascimento='1990-01-01')
        response = self.client.post(url, values, follow=True)
        self.assertContains(response, 'Informações atualizadas com sucesso.')
        self.patient_user.refresh_from_db()
        self.assertEqual(self.patient_user.email, values['email'])
        values['email'] = 'inválido'
        response = self.client.post(url, values)
        self.assertContains(response, 'errorlist')
        self.assertNotContains(response, 'Informações atualizadas com sucesso.')
        self.patient_user.refresh_from_db()
        self.assertEqual(self.patient_user.email, 'novo@example.com')

    def test_exames_migration_idempotente_preserva_edicoes(self):
        migration = import_module('consultas.migrations.0006_exames_padrao')
        for nome, especialidade in migration.EXAMES:
            self.assertEqual(Exame.objects.get(nome=nome).especialidade_responsavel, especialidade)
        Exame.objects.filter(nome='Hemograma').update(especialidade_responsavel='Editada', ativo=False)
        total = Exame.objects.count()
        with connection.schema_editor(atomic=False) as editor:
            migration.criar_exames(apps, editor)
            migration.criar_exames(apps, editor)
        self.assertEqual(Exame.objects.count(), total)
        self.assertEqual(Exame.objects.get(nome='Hemograma').especialidade_responsavel, 'Editada')
        self.assertFalse(Exame.objects.get(nome='Hemograma').ativo)

    def test_consulta_exige_mfa(self):
        consulta = Consulta.objects.create(medico=self.doctor, paciente=self.patient, data_hora=self.time)
        self.client.force_login(self.doctor_user)
        self.assertEqual(self.client.get(reverse('medicos:detalhe_consulta', args=[consulta.pk])).status_code, 302)
