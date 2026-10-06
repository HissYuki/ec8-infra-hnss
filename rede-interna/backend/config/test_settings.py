"""O Client do Django testa views diretamente por HTTP, sem passar pela DMZ.

A integração real HTTPS/CSRF é validada separadamente pelo teste de navegador.
"""
from .settings import *  # noqa: F403

SECURE_SSL_REDIRECT = False
