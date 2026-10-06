"""Run inside the manager; credentials stay in its environment, never output."""
import base64
import json
import os
import ssl
import sys
import time
import urllib.request

context = ssl.create_default_context(cafile='/etc/ssl/root-ca.pem')
def request(url, username, password, body=None):
    credential = base64.b64encode(f'{username}:{password}'.encode()).decode()
    headers = {'Authorization': f'Basic {credential}', 'Content-Type': 'application/json'}
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, context=context, timeout=15) as response:
        return json.load(response)

marker = sys.argv[1]
query = {'size': 20, 'query': {'term': {'data.test_id': marker}}}
deadline = time.monotonic() + 180
while time.monotonic() < deadline:
    try:
        result = request('https://wazuh.indexer:9200/wazuh-alerts-*/_search',
                         os.environ['INDEXER_USERNAME'], os.environ['INDEXER_PASSWORD'], query)
        agents = {hit['_source']['agent']['name'] for hit in result['hits']['hits']}
        if agents >= {'lab-dmz', 'lab-dados', 'lab-endpoints'}:
            print('PASS: authenticated agents in VLAN 10/20/40 sent events indexed with TLS.')
            break
    except Exception:
        pass
    time.sleep(5)
else:
    raise SystemExit('FAIL: all three indexed test events were not received within 180 seconds.')

deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    try:
        api = request('https://localhost:55000/security/user/authenticate',
                      os.environ['API_USERNAME'], os.environ['API_PASSWORD'], {})
        break
    except Exception:
        time.sleep(5)
else:
    raise SystemExit('FAIL: manager API unavailable or credentials rejected.')
token = api['data']['token']
req = urllib.request.Request('https://localhost:55000/agents?status=active',
                             headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req, context=context, timeout=15) as response:
    names = {agent['name'] for agent in json.load(response)['data']['affected_items']}
if not {'lab-dmz', 'lab-dados', 'lab-endpoints'} <= names:
    raise SystemExit('FAIL: laboratory agents not active in manager API.')
print('PASS: manager API verified over TLS; three agents active.')

deadline = time.monotonic() + 180
while time.monotonic() < deadline:
    result = request('https://wazuh.indexer:9200/wazuh-alerts-*/_search',
                     os.environ['INDEXER_USERNAME'], os.environ['INDEXER_PASSWORD'],
                     {'size': 50, 'query': {'bool': {'filter': [
                         {'term': {'syscheck.path': '/monitor/canary/baseline.txt'}},
                         {'range': {'timestamp': {'gte': 'now-5m'}}}
                     ]}}})
    records = [hit['_source'] for hit in result['hits']['hits']]
    names = {record['agent']['name'] for record in records}
    if names >= {'lab-dmz', 'lab-dados', 'lab-endpoints'}:
        assert all('diff' not in record.get('syscheck', {}) for record in records)
        print('PASS: FIM detected benign changes in all three agents without recording file contents.')
        break
    time.sleep(5)
else:
    raise SystemExit('FAIL: three FIM alerts were not indexed within 180 seconds.')
