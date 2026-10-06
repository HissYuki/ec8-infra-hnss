import json
from types import SimpleNamespace

from django.test import SimpleTestCase

from .security_audit import audit, failed_event

class SecurityAuditTests(SimpleTestCase):
    def test_audit_never_serializes_user_or_credentials(self):
        user = SimpleNamespace(tipo='PACIENTE', username='private-patient',
                               email='private@example.com', password='secret', token='123456')
        with self.assertLogs('hospital.security', level='INFO') as captured:
            audit('mfa_verified', user)
            failed_event(None, credentials={'username': user.username, 'password': user.password})
        events = [json.loads(record.getMessage()) for record in captured.records]
        self.assertEqual(events[0], {'source': 'hospital.security',
                                    'event': 'mfa_verified', 'role': 'PACIENTE'})
        self.assertEqual(events[1]['event'], 'password_login_failed')
        for secret in ('private-patient', 'private@example.com', 'secret', '123456'):
            self.assertNotIn(secret, '\n'.join(captured.output))

    def test_free_text_events_are_rejected(self):
        with self.assertRaises(ValueError):
            audit('password=secret')
