import os, json, urllib.request
from pathlib import Path

for line in Path('web_demo/.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")

url = os.environ['SUPABASE_URL']
key = os.environ['SUPABASE_SECRET_KEY']
hdr = {'apikey': key, 'Authorization': 'Bearer ' + key}

req = urllib.request.Request(url + '/rest/v1/', headers=hdr)
spec = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())

paths = {}
for p, ops in spec.get('paths', {}).items():
    if p.startswith('/rpc/'):
        name = p[5:]
        params = []
        for method, op in ops.items():
            for param in op.get('parameters', []):
                if param.get('in') == 'query' and param.get('name') not in ('select', 'columns'):
                    params.append(param['name'])
        paths.setdefault(name, []).append(sorted(params))

overloaded = {n: v for n, v in paths.items() if len(v) > 1}
if overloaded:
    print("OVERLOADED RPC FUNCTIONS (need drop):")
    for name, variants in sorted(overloaded.items()):
        print(f"  {name}")
        for variant in variants:
            print(f"      ({', '.join(variant)})")
else:
    print("No overloaded RPC functions detected.")

print()
print("All RPC functions:")
for name in sorted(paths):
    for variant in paths[name]:
        print(f"  {name}({', '.join(variant)})")
