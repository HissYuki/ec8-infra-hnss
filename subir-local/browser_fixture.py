"""Dados descartáveis do teste de integração local; não é uma funcionalidade web."""
import json
import os
import secrets
import sys
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from accounts.models import User
from pacientes.models import Paciente
from medicos.models import Medico
from coordenador.models import Coordenador
from consultas.models import Consulta, HorarioDisponivel, HorarioExameDisponivel, Exame
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.oath import totp

action, prefix = sys.argv[1:3]
if not prefix.startswith('hospital_integration_') or not prefix.replace('_', '').isalnum():
    raise ValueError('Prefixo de teste inválido')
if action == 'setup':
    password = secrets.token_urlsafe(24)
    users = {}
    for role in ('PACIENTE', 'MEDICO', 'COORDENADOR', 'ADMIN'):
        kwargs = dict(username=f'{prefix}_{role}', email=f'{prefix}_{role}@example.com',
                      first_name='Teste', last_name=role, password=password)
        users[role] = (User.objects.create_superuser(**kwargs) if role == 'ADMIN'
                       else User.objects.create_user(tipo=role, **kwargs))
    patient = Paciente.objects.create(usuario=users['PACIENTE'], data_nascimento='1990-01-01')
    doctor = Medico.objects.create(usuario=users['MEDICO'], crm=prefix[-15:], especialidade='Cardiologia')
    coordinator = Coordenador.objects.create(usuario=users['COORDENADOR'], matricula=prefix[-15:])
    date = (timezone.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    HorarioDisponivel.objects.create(medico=doctor, data_hora=date)
    other_user = User.objects.create_user(username=f'{prefix}_ALVO', tipo='PACIENTE',
        first_name='Paciente', last_name='Sintético', password=password)
    other_patient = Paciente.objects.create(usuario=other_user)
    appointment = Consulta.objects.create(medico=doctor, paciente=other_patient, data_hora=date + timedelta(hours=1))
    HorarioExameDisponivel.objects.create(medico_responsavel=doctor, coordenador=coordinator,
        exame=Exame.objects.get(nome='Eletrocardiograma'), data_hora=date + timedelta(hours=2))
    print(json.dumps(dict(password=password, users={r:u.username for r,u in users.items()},
        doctor=doctor.pk, appointment=appointment.pk, date=timezone.localtime(date).date().isoformat())))
elif action == 'token':
    device = TOTPDevice.objects.get(user__username=f'{prefix}_{sys.argv[3]}')
    print(json.dumps(str(totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits)).zfill(6)))
elif action == 'cleanup':
    Consulta.objects.filter(medico__usuario__username__startswith=prefix).delete()
    HorarioExameDisponivel.objects.filter(coordenador__usuario__username__startswith=prefix).delete()
    User.objects.filter(username__startswith=prefix).delete()
    print('{}')
else:
    raise ValueError('Operação inválida')
