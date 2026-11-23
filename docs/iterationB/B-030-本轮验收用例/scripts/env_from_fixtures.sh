#!/usr/bin/env bash
# Source this after prepare_fixtures.py succeeded.
# Usage: set -a; source runs/.env.local; set +a; source scripts/env_from_fixtures.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IDS="$ROOT/runs/fixture-ids.json"
ENVF="$ROOT/runs/.env.local"
if [[ ! -f "$ENVF" ]]; then
  echo "missing $ENVF" >&2
  return 1 2>/dev/null || exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENVF"; set +a
if [[ ! -f "$IDS" ]]; then
  echo "missing $IDS — run prepare_fixtures.py" >&2
  return 1 2>/dev/null || exit 1
fi
READY=$(python3 -c "import json;print(json.load(open('$IDS')).get('ready'))")
if [[ "$READY" != "True" && "$READY" != "true" ]]; then
  echo "fixtures not ready" >&2
  python3 -c "import json;print(json.load(open('$IDS')))" >&2
  return 1 2>/dev/null || exit 1
fi
eval "$(python3 - <<'PY'
import json
from pathlib import Path
ids=json.loads(Path("'"$IDS"'").read_text())
print(f"export BASE={ids['base_url']!r}")
print(f"export B030_BASE_URL={ids['base_url']!r}")
print(f"export B030_DB_NAME={ids['db']!r}")
print(f"export B030_SUT_SHA={ids.get('sut_sha') or ''!r}")
for code,p in ids['products'].items():
    if 'productId' in p:
        safe=code.replace('-','_')
        print(f"export PID_{safe}={p['productId']!r}")
# convenience aliases
m={
 'P_ON_10':'PID_P_ON_10','P_ON_5':'PID_P_ON_5','P_ON_1':'PID_P_ON_1',
 'P_ON_0':'PID_P_ON_0','P_OFF_M':'PID_P_OFF_M','P_BIG':'PID_P_BIG'
}
# also short names used in docs
prods=ids['products']
print(f"export PID_ON10={prods['P-ON-10']['productId']!r}")
print(f"export PID_ON5={prods['P-ON-5']['productId']!r}")
print(f"export PID_ON1={prods['P-ON-1']['productId']!r}")
print(f"export PID_OFFM={prods['P-OFF-M']['productId']!r}")
print(f"export PID_ZERO={prods['P-ON-0']['productId']!r}")
print(f"export PID_BIG={prods['P-BIG']['productId']!r}")
PY
)"

login_json() {
  curl -sS -X POST "$BASE$1" -H 'Content-Type: application/json' -d "$2"
}
export TA=$(login_json /api/auth/login '{"username":"b030_buyer_a","password":"B030-BuyerA-Pass9"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['token'])")
export TB=$(login_json /api/auth/login '{"username":"b030_buyer_b","password":"B030-BuyerB-Pass9"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['token'])")
export TS=$(login_json /api/admin/auth/login "{\"username\":\"admin\",\"password\":\"$B030_SELLER_PASSWORD\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['token'])")
echo "env ready BASE=$BASE SUT=$B030_SUT_SHA PID_ON10=$PID_ON10 TA/TB/TS set"
