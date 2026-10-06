"""Verificações de comunicação autorizada e isolamento do ambiente LOCAL."""
import json
import os
import subprocess
from pathlib import Path


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def inspect(name):
    return json.loads(docker('inspect', name))[0]


backend = inspect('hospital-interna-backend-1')
database = inspect('dados-postgres')
frontend = inspect('hospital-dmz-nginx-web-1')
proxy = inspect('hospital-dmz-nginx-proxy-1')
waf = inspect('hospital-dmz-modsecurity-waf-1')
manager = inspect('hospital-interna-wazuh-manager-1')
indexer = inspect('hospital-interna-wazuh-indexer-1')
dashboard = inspect('hospital-interna-wazuh-dashboard-1')
agent_dmz = inspect('hospital-dmz-wazuh-agent-dmz-1')
agent_dados = inspect('hospital-interna-wazuh-agent-dados-1')
agent_endpoints = inspect('hospital-interna-wazuh-agent-endpoints-1')
db_network = 'hospital-interna_db_app'
assert db_network in backend['NetworkSettings']['Networks']
assert set(database['NetworkSettings']['Networks']) == {db_network}
assert not database['HostConfig']['PortBindings']
assert not backend['HostConfig']['PortBindings']
assert 'hospital-local-transit' in frontend['NetworkSettings']['Networks']
assert 'hospital-dmz_frontend_link' in frontend['NetworkSettings']['Networks']
assert 'hospital-dmz_frontend_link' in waf['NetworkSettings']['Networks']
for service in (frontend, proxy, waf):
    assert db_network not in service['NetworkSettings']['Networks']
assert 'hospital-local-transit' not in proxy['NetworkSettings']['Networks']
assert 'hospital-local-transit' not in waf['NetworkSettings']['Networks']
for service in (manager, indexer, dashboard, agent_dmz):
    assert db_network not in service['NetworkSettings']['Networks']
assert not indexer['HostConfig']['PortBindings']
assert '55000/tcp' not in manager['HostConfig']['PortBindings']
assert set(indexer['NetworkSettings']['Networks']) == {'hospital-interna_wazuh_core'}
assert not agent_dmz['HostConfig']['Privileged']
assert all(mount['Destination'] != '/var/run/docker.sock' for mount in agent_dmz['Mounts'])
for agent, network in (
    (agent_dmz, 'hospital-dmz_vlan10'),
    (agent_dados, 'hospital-interna_vlan20'),
    (agent_endpoints, 'hospital-interna_vlan40'),
):
    assert set(agent['NetworkSettings']['Networks']) == {network, 'hospital-wazuh-transit'}
    assert not agent['HostConfig']['Privileged']
    assert all(mount['Destination'] != '/var/run/docker.sock' for mount in agent['Mounts'])

db_ip = database['NetworkSettings']['Networks'][db_network]['IPAddress']
backend_ip = backend['NetworkSettings']['Networks']['hospital-local-transit']['IPAddress']
# Teste apenas de conectividade TCP, sem autenticação ou leitura de dados.
for network, destination, port in (
    ('hospital-dmz_backend_egress', db_ip, 5432),
    ('hospital-dmz_vlan10', backend_ip, 8444),
    ('hospital-wazuh-transit', db_ip, 5432),
    ('hospital-wazuh-transit', indexer['NetworkSettings']['Networks']['hospital-interna_wazuh_core']['IPAddress'], 9200),
):
    source = f'''import socket
try:
    socket.create_connection(({destination!r}, {port}), timeout=2)
except OSError:
    print('Conexão não autorizada bloqueada')
else:
    raise SystemExit('FALHA: conexão não autorizada permitida')
'''
    print(docker('run', '--rm', '--network', network, 'python:3.13-slim', 'python', '-c', source))

# Um peer sem certificado de cliente não pode acessar o Django nem na rede correta.
source = '''import socket, ssl
context = ssl.create_default_context(cafile='/tmp/backend-ca.crt')
try:
    with context.wrap_socket(socket.create_connection(('hospital-backend', 8444), timeout=3),
                             server_hostname='hospital-backend') as connection:
        connection.sendall(b'GET / HTTP/1.1\\r\\nHost: localhost\\r\\nConnection: close\\r\\n\\r\\n')
        response = connection.recv(1024)
except ssl.SSLError as error:
    assert error.reason in ('TLSV13_ALERT_CERTIFICATE_REQUIRED', 'SSLV3_ALERT_HANDSHAKE_FAILURE'), error.reason
    print('Backend recusou cliente sem certificado')
else:
    assert not response.startswith(b'HTTP/'), 'Backend aceitou cliente sem certificado'
    print('Backend encerrou conexão sem certificado')
'''
host_root = os.environ.get('HOSPITAL_HOST_ROOT')
ca = (host_root.replace(chr(92), '/') + '/subir-local/tls/backend-ca.crt'
      if host_root else Path(__file__).resolve().parent / 'tls' / 'backend-ca.crt')
print(docker('run', '--rm', '--network', 'hospital-local-transit',
             '--mount', f'type=bind,source={ca},target=/tmp/backend-ca.crt,readonly',
             'python:3.13-slim', 'python', '-c', source))
print('Topologia, portas e TLS mútuo: OK')
