"""
Test all discovered /portal/ API endpoints
"""
import requests
import json
import hashlib
import hmac
import time

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0', 'Origin': 'https://urja-ops.flockenergy.tech'})
BASE = 'https://urja-ops.flockenergy.tech'

def login():
    s.get(BASE + '/login')
    r = s.post(BASE + '/login', data={'email': 'operator@urja.local', 'password': 'urja-ops-2026'},
        headers={'Content-Type': 'application/x-www-form-urlencoded', 
                 'Origin': 'https://urja-ops.flockenergy.tech'},
        allow_redirects=False)
    print('Login:', r.status_code, list(s.cookies.keys()))

login()

print('\n=== Portal API endpoints ===\n')

# 1. Meters search
r = s.get(BASE + '/portal/meters/search?q=&page=1')
print(f'GET /portal/meters/search?q=&page=1: {r.status_code} {r.headers.get("content-type")}')
if r.status_code == 200:
    d = r.json()
    print(f'  total: {d.get("total")}')
    print(f'  data[0]: {json.dumps(d.get("data", [])[0] if d.get("data") else None, indent=2)}')

# 2. DTs list
r2 = s.get(BASE + '/portal/dts?page=1')
print(f'\nGET /portal/dts?page=1: {r2.status_code} {r2.headers.get("content-type")}')
if r2.status_code == 200:
    d = r2.json()
    print(f'  total: {d.get("total")}')
    print(f'  data[0]: {json.dumps(d.get("data", [])[0] if d.get("data") else None, indent=2)}')

# 3. Keys endpoint
r3 = s.get(BASE + '/portal/keys')
print(f'\nGET /portal/keys: {r3.status_code} {r3.headers.get("content-type")}')
if r3.status_code == 200:
    d = r3.json()
    print(f'  Response: {json.dumps(d, indent=2)}')
    signing_secret = d.get('data', {}).get('signingSecret', '')
    print(f'  signingSecret: {signing_secret[:20]}...')
else:
    print(f'  Body: {r3.text[:500]}')
    signing_secret = ''

# 4. Meter geo
r4 = s.get(BASE + '/portal/meters/J100000/geo')
print(f'\nGET /portal/meters/J100000/geo: {r4.status_code} {r4.headers.get("content-type")}')
if r4.status_code == 200:
    print(f'  {json.dumps(r4.json(), indent=2)[:500]}')

# 5. Meter energy
r5 = s.get(BASE + '/portal/meters/J100000/energy')
print(f'\nGET /portal/meters/J100000/energy: {r5.status_code} {r5.headers.get("content-type")}')
if r5.status_code == 200:
    d = r5.json()
    print(f'  data count: {len(d.get("data", []))}')
    if d.get("data"):
        print(f'  data[0]: {json.dumps(d["data"][0], indent=2)}')

# 6. Try export with HMAC
if signing_secret:
    method = 'GET'
    path = '/portal/export'
    query = 'page=1'
    timestamp = str(int(time.time()))
    message = f'{method}\n{path}\n{query}\n{timestamp}'
    sig = hmac.new(signing_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    
    r6 = s.get(BASE + '/portal/export?page=1', headers={
        'x-timestamp': timestamp,
        'x-signature': sig,
    })
    print(f'\nGET /portal/export?page=1 (HMAC signed): {r6.status_code} {r6.headers.get("content-type")}')
    if r6.status_code == 200:
        d = r6.json()
        print(f'  total: {d.get("total")}')
        print(f'  data count: {len(d.get("data", []))}')
        if d.get("data"):
            print(f'  data[0]: {json.dumps(d["data"][0], indent=2)}')
    else:
        print(f'  Body: {r6.text[:500]}')
else:
    print('\nSkipping export test (no signing secret)')

# 7. Other portal endpoints to try
other_endpoints = [
    '/portal/meters',
    '/portal/meters/J100000',
    '/portal/meters/search',
    '/portal/network',
    '/portal/hierarchy',
    '/portal/feeders',
    '/portal/substations',
    '/portal/dts',
]
print('\n=== Other portal endpoints ===')
for ep in other_endpoints:
    rv = s.get(BASE + ep, allow_redirects=False)
    print(f'{ep}: {rv.status_code} {rv.headers.get("content-type", "?")}')
    if rv.status_code == 200 and 'json' in rv.headers.get('content-type', ''):
        print(f'  {rv.text[:200]}')
