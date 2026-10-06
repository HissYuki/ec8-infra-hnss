"""Prepare LOCAL certificates and password hashes without exposing secrets."""
import json
import os
from pathlib import Path
import subprocess

import bcrypt

os.umask(0o077)
if int(Path('/proc/sys/vm/max_map_count').read_text()) < 262144:
    raise SystemExit('Wazuh requires vm.max_map_count >= 262144 on the Docker Linux host.')
root = Path('/runtime')
root.mkdir(exist_ok=True)
env = {}
for line in Path('/setup.env').read_text(encoding='utf-8-sig').splitlines():
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        env[key] = value

def write(name, content, mode=0o600):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    path.chmod(mode)

def openssl(*args):
    subprocess.run(['openssl', *args], cwd=root, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

if not (root / 'certs/root-ca.pem').exists():
    (root / 'certs').mkdir(exist_ok=True)
    openssl('req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-days', '30',
            '-keyout', 'certs/root-ca.key', '-out', 'certs/root-ca.pem',
            '-subj', '/CN=Hospital Wazuh Local CA',
            '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    for name in ('wazuh.indexer', 'wazuh.manager', 'wazuh.dashboard', 'admin'):
        openssl('req', '-newkey', 'rsa:2048', '-nodes',
                '-keyout', f'certs/{name}-key.pem', '-out', f'certs/{name}.csr',
                '-subj', f'/CN={name}/OU=Wazuh/O=Wazuh/L=California/C=US')
        extensions = ('keyUsage=critical,digitalSignature,keyEncipherment\n'
                      'extendedKeyUsage=serverAuth,clientAuth\n'
                      f'subjectAltName=DNS:{name},DNS:localhost,IP:127.0.0.1\n')
        write('certs/extensions', extensions)
        openssl('x509', '-req', '-in', f'certs/{name}.csr',
                '-CA', 'certs/root-ca.pem', '-CAkey', 'certs/root-ca.key',
                '-CAcreateserial', '-days', '30', '-out', f'certs/{name}.pem',
                '-extfile', 'certs/extensions')
    for path in (root / 'certs').glob('*.pem'):
        path.chmod(0o640 if '-key.' in path.name else 0o644)
        # Indexer/dashboard run as UID 1000; CA key remains root only.
        os.chown(path, 1000, 1000)
    os.chown(root / 'certs/root-ca.key', 0, 0)
    (root / 'certs/root-ca.key').chmod(0o600)
else:
    openssl('x509', '-checkend', '0', '-noout', '-in', 'certs/root-ca.pem')

# Do not silently rotate passwords/hash material for initialized volumes.
users_file = root / 'internal_users.yml'
if not users_file.exists():
    users = {'_meta': {'type': 'internalusers', 'config_version': 2}}
    for name, variable, role in (
            ('admin', 'WAZUH_INDEXER_ADMIN_PASSWORD', 'admin'),
            ('kibanaserver', 'WAZUH_DASHBOARD_PASSWORD', 'kibana_server')):
        password = env[variable]
        if not password or password.startswith('SUBSTITUA'):
            raise SystemExit(f'Configure {variable}; no default credentials allowed.')
        users[name] = {'hash': bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                       'reserved': True, 'backend_roles': [role]}
    write('internal_users.yml', json.dumps(users, indent=2), 0o640)
    os.chown(users_file, 1000, 1000)
else:
    users = json.loads(users_file.read_text())
    for name, variable in (('admin', 'WAZUH_INDEXER_ADMIN_PASSWORD'),
                           ('kibanaserver', 'WAZUH_DASHBOARD_PASSWORD')):
        if not bcrypt.checkpw(env[variable].encode(), users[name]['hash'].encode()):
            raise SystemExit('Existing Wazuh credentials differ; use a coordinated rotation.')

write('authd.pass', env['WAZUH_ENROLLMENT_PASSWORD'] + '\n', 0o640)
os.chown(root / 'authd.pass', 0, 999)
write('wazuh.yml', json.dumps({'hosts': [{'1513629884013': {
    'url': 'https://wazuh.manager', 'port': 55000, 'username': 'wazuh-wui',
    'password': env['WAZUH_API_PASSWORD'], 'run_as': True}}]}, indent=2), 0o640)
os.chown(root / 'wazuh.yml', 1000, 1000)
for area in ('dmz', 'dados', 'endpoints'):
    directory = root / 'canary' / area
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'baseline.txt').touch(exist_ok=True)
    (directory / 'events.jsonl').touch(exist_ok=True)
print('Wazuh local material prepared; existing keys and passwords preserved.')
