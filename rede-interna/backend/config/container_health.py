"""Readiness sem endpoint público, sessão ou segredo TOTP."""
import os
import socket

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.db import connection

with socket.create_connection(('127.0.0.1', int(os.environ.get('BACKEND_PORT', '8444'))), timeout=3):
    pass
with connection.cursor() as cursor:
    cursor.execute('SELECT 1')
    assert cursor.fetchone() == (1,)
