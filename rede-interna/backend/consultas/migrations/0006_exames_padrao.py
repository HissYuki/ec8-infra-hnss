from django.db import migrations


EXAMES = (
    ('Eletrocardiograma', 'Cardiologia'),
    ('Ecocardiograma', 'Cardiologia'),
    ('Hemograma', 'Bioquímico'),
    ('TSH / Hormonal', 'Bioquímico'),
    ('Raio-X', 'Radiologista'),
    ('Tomografia', 'Radiologista'),
    ('Ultrassom', 'Radiologista'),
    ('Endoscopia', 'Gastroenterologista'),
    ('Colonoscopia', 'Gastroenterologista'),
)


def criar_exames(apps, schema_editor):
    Exame = apps.get_model('consultas', 'Exame')
    for nome, especialidade in EXAMES:
        Exame.objects.using(schema_editor.connection.alias).get_or_create(
            nome=nome, defaults={'especialidade_responsavel': especialidade, 'ativo': True},
        )


class Migration(migrations.Migration):
    dependencies = [('consultas', '0005_remove_agendamentoexame_agendamento_exame_unico_horario_and_more')]
    # O rollback não apaga exames que possam ter sido editados ou utilizados.
    operations = [migrations.RunPython(criar_exames, migrations.RunPython.noop)]
