"""Exercise server orchestration with a fake Docker; never touches real volumes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DeploymentScriptsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.log = self.work / 'commands.jsonl'
        executable = self.work / 'docker'
        executable.write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['DOCKER_TEST_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
''')
        executable.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.work) + ':' + os.environ['PATH'],
                        DOCKER_TEST_LOG=str(self.log))
        self.envfile = self.work / 'server.env'
        self.env['ENV_FILE'] = str(self.envfile)

    def prepare(self, machine):
        example = ROOT / 'subir-servidor' / machine / '.env.example'
        values = {}
        for line in example.read_text().splitlines():
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                values[key] = 'fixture-value' if 'SUBSTITUA' in value else value
        values.update(PUBLIC_HOST='hospital.example.org',
                      PUBLIC_ORIGIN='https://hospital.example.org',
                      DMZ_BIND_IP='192.168.10.10', BACKEND_BIND_IP='192.168.20.10',
                      WAZUH_BIND_IP='192.168.30.10',
                      BACKEND_URL='https://backend.example.org:8444',
                      TLS_DIR=str(self.work / 'tls'),
                      WAZUH_RUNTIME_DIR=str(self.work / 'wazuh'))
        for folder, files in {
            'tls': ['public.crt', 'public.key', 'backend-ca.crt', 'frontend.crt',
                    'frontend.key', 'backend.crt', 'backend.key', 'client-ca.crt'],
            'wazuh': ['authd.pass', 'internal_users.yml', 'wazuh.yml'],
            'wazuh/certs': ['root-ca.pem', 'wazuh.manager.pem', 'wazuh.manager-key.pem',
                            'wazuh.indexer.pem', 'wazuh.indexer-key.pem',
                            'wazuh.dashboard.pem', 'wazuh.dashboard-key.pem',
                            'admin.pem', 'admin-key.pem'],
        }.items():
            directory = self.work / folder
            directory.mkdir(parents=True, exist_ok=True)
            for name in files:
                (directory / name).write_text('fixture: not a certificate')
        self.envfile.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))

    def run_script(self, machine, *args):
        return subprocess.run(['bash', str(ROOT / 'subir-servidor' / machine / 'subir.sh'),
                               *args], env=self.env, cwd='/tmp', capture_output=True, text=True)

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_up_controls_only_its_machine_without_local_overrides_or_migrations(self):
        for machine, project in [('DMZ', 'hospital-dmz'), ('Rede Interna', 'hospital-interna')]:
            with self.subTest(machine=machine):
                self.prepare(machine)
                self.log.unlink(missing_ok=True)
                result = self.run_script(machine, 'up')
                self.assertEqual(result.returncode, 0, result.stderr)
                for command in self.commands():
                    if command[:2] == ['compose', 'version']:
                        continue
                    self.assertIn(project, command)
                    self.assertNotIn('migrate', command)
                    self.assertNotIn('--volumes', command)
                    self.assertNotIn('-v', command)
                    self.assertFalse(any('compose.local' in arg for arg in command))

    def test_down_preserves_volumes(self):
        self.prepare('Rede Interna')
        self.assertEqual(self.run_script('Rede Interna', 'down').returncode, 0)
        self.assertEqual(self.commands()[-1][-1], 'down')
        self.assertNotIn('-v', self.commands()[-1])

    def test_migrations_are_explicit_and_internal_only(self):
        self.prepare('Rede Interna')
        self.assertEqual(self.run_script('Rede Interna', 'migrate').returncode, 0)
        self.assertEqual(self.commands()[-1][-4:], ['python', 'manage.py', 'migrate', '--noinput'])
        self.assertNotEqual(self.run_script('DMZ', 'migrate').returncode, 0)

    def test_missing_configuration_and_extra_flags_are_rejected(self):
        self.assertNotEqual(self.run_script('DMZ', 'up').returncode, 0)
        self.prepare('DMZ')
        self.envfile.write_text(self.envfile.read_text().replace('hospital.example.org', 'SUBSTITUA'))
        self.assertNotEqual(self.run_script('DMZ', 'up').returncode, 0)
        self.assertNotEqual(self.run_script('DMZ', 'down', '-v').returncode, 0)

    def test_default_action_only_reads_status(self):
        self.prepare('DMZ')
        self.assertEqual(self.run_script('DMZ').returncode, 0)
        self.assertEqual(self.commands()[-1][-1], 'ps')


if __name__ == '__main__':
    unittest.main()
