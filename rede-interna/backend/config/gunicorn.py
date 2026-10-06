"""WSGI independente; TLS mútuo obrigatório no ambiente integrado."""
import os
import ssl

bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')
workers = int(os.environ.get('GUNICORN_WORKERS', '2'))
timeout = 60
accesslog = None
errorlog = '-'
forwarded_allow_ips = ''

if os.environ.get('BACKEND_MTLS', 'False').lower() == 'true':
    certfile = '/run/tls/backend.crt'
    keyfile = '/run/tls/backend.key'
    ca_certs = '/run/tls/client-ca.crt'
    cert_reqs = ssl.CERT_REQUIRED

    def ssl_context(conf, default_factory):
        context = default_factory()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context
