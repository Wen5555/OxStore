"""Verify the iteration-2 + auction Docker bundle with real containers.

Starts an isolated Compose project from an exported bundle (random project name, port and
volumes), drives the real Nginx -> Spring Boot -> MySQL stack through the public HTTP API and
removes the project afterwards. No mocked API, no manual clock and no direct scheduler call:
auctions are closed by the application's own 5-second scan.

Credentials are generated per run and are never written to the result file.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import threading
import time
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

VERSION = os.environ.get('OXSTORE_VERSION', '0.1.0-iteration2-auction-docker.1')
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')


class Check:
    def __init__(self, bundle: Path, output: Path, keep: bool):
        self.bundle, self.output, self.keep = bundle.resolve(), output.resolve(), keep
        self.output.mkdir(parents=True, exist_ok=True)
        self.project = 'oxstore-iter2-test-' + uuid.uuid4().hex[:12]
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]
        self.admin_password = 'Ox!' + secrets.token_hex(16)
        self.customer_password = 'Cu!' + secrets.token_hex(8)
        self.env = dict(os.environ, COMPOSE_PROJECT_NAME=self.project, APP_PORT=str(self.port),
                        APP_BIND_ADDRESS='127.0.0.1', DB_PASSWORD=secrets.token_hex(32),
                        JWT_SECRET=secrets.token_hex(32), ADMIN_INITIAL_PASSWORD=self.admin_password,
                        OXSTORE_VERSION=VERSION)
        self.base = f'http://127.0.0.1:{self.port}'
        self.report = {'run_at': datetime.now().astimezone().isoformat(), 'project': self.project,
                       'version': VERSION,
                       'scope': 'Real Compose / Nginx / Java17 / MySQL8 / persistent volumes; auction closed by the '
                                'application scheduler',
                       'checks': [], 'requests': []}
        self.seller = ''

    # ---------- infrastructure ----------
    def compose(self, *args, check=True, timeout=300):
        result = subprocess.run(['docker', 'compose', '-f', str(self.bundle / 'compose.yml'), '-p', self.project, *args],
                                cwd=self.bundle, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout)
        text = result.stdout.decode('utf-8', errors='replace')
        with (self.output / 'compose-operations.log').open('a', encoding='utf-8') as log:
            log.write('docker compose ' + ' '.join(args) + '\n' + text + '\n')
        if check and result.returncode:
            raise RuntimeError(text[-2500:])
        return text

    def up(self):
        self.compose('up', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '240')

    def check(self, name, condition, detail):
        self.report['checks'].append({'name': name, 'status': 'PASS' if condition else 'FAIL', 'detail': detail})
        print(('PASS ' if condition else 'FAIL ') + name + ': ' + detail, flush=True)
        if not condition:
            raise AssertionError(name)

    def api(self, method, path, data=None, token=None, expected=200, files=None):
        headers = {}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if files is None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(data).encode('utf-8') if data is not None else None
        else:
            boundary = 'oxstore-' + uuid.uuid4().hex
            parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                     for k, v in (data or {}).items()]
            for filename, content in files:
                parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="images"; filename="{filename}"\r\n'
                              'Content-Type: image/png\r\n\r\n').encode() + content + b'\r\n')
            body = b''.join(parts) + f'--{boundary}--\r\n'.encode()
            headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
        try:
            with urlopen(Request(self.base + path, data=body, headers=headers, method=method), timeout=30) as r:
                status, raw = r.status, r.read()
        except HTTPError as e:
            status, raw = e.code, e.read()
        route = re.sub(r'/\d+(?=/|$|\?)', '/{id}', path.split('?', 1)[0])
        self.report['requests'].append({'method': method, 'path': route, 'status': status})
        if status != expected:
            raise AssertionError(f'{method} {route}: HTTP {status}, expected {expected}: {raw[:200]!r}')
        value = json.loads(raw) if raw else {}
        return value

    def data(self, *args, **kwargs):
        return self.api(*args, **kwargs).get('data')

    def register(self, name, phone):
        self.api('POST', '/api/auth/register', {'username': name, 'password': self.customer_password, 'phone': phone},
                 expected=201)
        return self.data('POST', '/api/auth/login', {'username': name, 'password': self.customer_password})['token']

    def sse(self, path, token, wanted, seconds=20):
        """Read an SSE stream through Nginx; return {event_name: seconds_after_open}."""
        seen, opened = {}, time.monotonic()

        def run():
            try:
                req = Request(self.base + path, headers={'Authorization': 'Bearer ' + token,
                                                         'Accept': 'text/event-stream'})
                with urlopen(req, timeout=seconds) as r:
                    for raw in r:
                        line = raw.decode('utf-8', errors='replace').strip()
                        if line.startswith('event:'):
                            seen.setdefault(line[6:].strip(), time.monotonic() - opened)
                        if wanted <= set(seen) or time.monotonic() - opened > seconds:
                            return
            except Exception as e:  # timeout or reset: whatever arrived is reported
                seen.setdefault('_error', type(e).__name__)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return seen, thread

    # ---------- scenario ----------
    def snapshot_state(self, ids):
        state = {}
        for key, product in ids.items():
            snap = self.data('GET', f'/api/products/{product}/auction')
            snap.pop('serverTime', None)
            state[key] = snap
        return state

    def flow(self):
        self.compose('config', '-q')
        self.up()
        ps = [json.loads(line) for line in self.compose('ps', '--format', 'json').splitlines() if line.startswith('{')]
        self.check('D01', len(ps) == 3 and all(s.get('Health') == 'healthy' for s in ps),
                   'mysql, backend and frontend healthy; no build or registry pull')
        self.check('D02', all(not any(p.get('PublishedPort', 0) for p in s.get('Publishers') or [])
                              for s in ps if s['Service'] != 'frontend'), 'only the frontend port is published')
        for path in ['/', '/admin/login']:
            with urlopen(self.base + path, timeout=20) as r:
                self.check('D03' + path.replace('/', '_'), r.status == 200 and '<div id="root"></div>' in r.read().decode(),
                           'SPA route served by Nginx')
        tree = self.data('GET', '/api/categories/tree')
        leaf = tree[0]['children'][0]['id']
        self.check('D04', bool(leaf), 'seeded two-level category tree available')
        self.api('POST', '/api/admin/auth/login', {'username': 'admin', 'password': 'wrong-password-1'}, expected=401)
        self.seller = self.data('POST', '/api/admin/auth/login',
                                {'username': 'admin', 'password': self.admin_password})['token']
        self.api('GET', '/api/admin/auctions', expected=401)
        self.check('D05', bool(self.seller), 'seller login with generated password; unauthenticated admin request rejected')

        tag = uuid.uuid4().hex[:6]
        buyer_a = self.register('a_' + tag, '13800000001')
        buyer_b = self.register('b_' + tag, '13800000002')
        buyer_c = self.register('c_' + tag, '13800000003')
        buyer_d = self.register('d_' + tag, '13800000004')

        # --- fixed-price regression (intent queue -> trade -> history) ---
        fixed = self.data('POST', '/api/admin/products',
                          {'name': 'Docker一口价-' + tag, 'price': '19.90', 'stock': 1, 'category2Id': leaf,
                           'descriptionHtml': '<p>容器回归</p>'}, self.seller, 201, files=[('p.png', PNG)])['productId']
        detail = json.dumps(self.api('GET', f'/api/products/{fixed}'))
        image = re.search(r'/api/images/[^"\\]+', detail)
        with urlopen(self.base + image.group(0), timeout=20) as r:
            self.image_bytes = r.read()
        self.check('D06', image is not None and self.image_bytes == PNG,
                   'fixed-price product published with an uploaded image served through Nginx')
        self.api('POST', f'/api/products/{fixed}/auction/bids', {'amount': '20.00'}, buyer_a, expected=409)
        intent_a = self.data('POST', f'/api/products/{fixed}/intents', token=buyer_a)['intentId']
        intent_b = self.data('POST', f'/api/products/{fixed}/intents', token=buyer_b)['intentId']
        self.api('POST', f'/api/admin/intents/{intent_a}/start', token=self.seller)
        self.api('POST', f'/api/admin/intents/{intent_b}/start', token=self.seller, expected=409)
        self.api('POST', f'/api/admin/intents/{intent_a}/success', token=self.seller)
        history_a = self.data('GET', '/api/me/order-history', token=buyer_a)
        self.check('D07', history_a['total'] == 1 and history_a['items'][0]['status'] == 'SUCCESS',
                   'FIXED_PRICE: bid rejected (40908); queue, single trade, success and buyer history unchanged')
        self.api('GET', f'/api/products/{fixed}', expected=404)

        # --- three auctions closed by the real scheduler ---
        ends = datetime.now(ZoneInfo('Asia/Shanghai')).replace(microsecond=0) + timedelta(seconds=75)

        def auction(name, start='10.00', inc='2.00'):
            return self.data('POST', '/api/admin/products',
                             {'name': f'{name}-{tag}', 'category2Id': leaf, 'sellingMode': 'AUCTION',
                              'startPrice': start, 'minIncrement': inc, 'endsAt': ends.strftime('%Y-%m-%dT%H:%M:%S')},
                             self.seller, 201, files=())['productId']
        sold, failed, unsold = auction('Docker拍卖成交'), auction('Docker拍卖失败履约'), auction('Docker拍卖流拍')
        ids = {'sold': sold, 'failed': failed, 'unsold': unsold}
        snap = self.data('GET', f'/api/products/{sold}/auction')
        self.check('D08', snap['auctionStatus'] == 'LIVE' and snap['sellingMode'] == 'AUCTION'
                   and snap['bidCount'] == 0 and float(snap['nextMinBid']) == 10.0
                   and snap['leaderAlias'] is None, 'anonymous public snapshot of a LIVE auction without bids')
        self.api('POST', f'/api/products/{sold}/intents', token=buyer_a, expected=409)
        self.api('POST', f'/api/products/{sold}/auction/bids', {'amount': '10.00'}, expected=401)
        self.api('POST', f'/api/products/{sold}/auction/bids', {'amount': '10.00'}, self.seller, expected=403)
        self.api('POST', f'/api/products/{sold}/auction/bids', {'amount': '10.123'}, buyer_a, expected=400)
        self.api('POST', f'/api/products/{sold}/auction/bids', {'amount': '9.00'}, buyer_a, expected=409)
        self.check('D09', True, 'AUCTION: no intent (409), anonymous 401, seller self-bid 403, bad scale 400, low bid 409')

        # SSE through Nginx: product stream must deliver the snapshot and later bid events promptly.
        seen, reader = self.sse(f'/api/products/{sold}/auction/stream', buyer_a, {'snapshot', 'bid'}, seconds=25)
        time.sleep(2)
        self.api('POST', f'/api/products/{sold}/auction/bids', {'amount': '10.00'}, buyer_a, expected=201)
        self.api('POST', f'/api/products/{sold}/auction/bids', {'amount': '12.00'}, buyer_b, expected=201)
        reader.join(timeout=30)
        self.report['sse'] = seen
        self.check('D10', 'snapshot' in seen and 'bid' in seen and seen['bid'] < 15,
                   f'SSE through Nginx delivered {sorted(k for k in seen if not k.startswith("_"))} '
                   f'(bid event after {seen.get("bid", float("nan")):.1f}s)')
        mine_a = self.data('GET', f'/api/products/{sold}/auction', token=buyer_a)
        mine_b = self.data('GET', f'/api/products/{sold}/auction', token=buyer_b)
        self.check('D11', mine_a['myStatus'] == 'OUTBID' and mine_b['myStatus'] == 'LEADING'
                   and mine_b['bidCount'] == 2 and mine_b['leaderAlias'] and 'b_' not in str(mine_b['leaderAlias']),
                   'A outbid, B leading, public leader alias masked')
        self.api('POST', f'/api/products/{failed}/auction/bids', {'amount': '10.00'}, buyer_c, expected=201)

        # Wait for the application's own 5-second scan to settle all three auctions.
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            states = {k: self.data('GET', f'/api/products/{p}/auction')['auctionStatus'] for k, p in ids.items()}
            if all(v != 'LIVE' for v in states.values()):
                break
            time.sleep(3)
        self.check('D12', states == {'sold': 'ENDED_SOLD', 'failed': 'ENDED_SOLD', 'unsold': 'ENDED_UNSOLD'},
                   f'scheduler settled by itself: {states}')
        self.api('POST', f'/api/products/{sold}/auction/bids', {'amount': '50.00'}, buyer_d, expected=409)

        listing = {i['productId']: i for i in self.data('GET', '/api/admin/auctions?page=1&size=100', token=self.seller)['items']}
        won = self.data('GET', f'/api/products/{sold}/auction', token=buyer_b)
        self.check('D13', won['myStatus'] == 'WON' and listing[sold]['winnerIntentId'] and listing[unsold].get('winnerIntentId') is None
                   and listing[failed]['winnerIntentId'], 'winner linked to a purchase intent; unsold auction has none')
        b_alerts = self.data('GET', '/api/me/auction-notifications?page=1&size=20', token=buyer_b)
        s_alerts = self.data('GET', '/api/admin/auction-notifications?page=1&size=50', token=self.seller)
        types = sorted(n['type'] for n in s_alerts['items'] if n['productId'] in ids.values())
        self.check('D14', [n['type'] for n in b_alerts['items']] == ['AUCTION_WON']
                   and types == ['AUCTION_SOLD', 'AUCTION_SOLD', 'AUCTION_UNSOLD'],
                   'winner gets one AUCTION_WON; seller gets two AUCTION_SOLD and one AUCTION_UNSOLD')
        public_unsold = self.api('GET', f'/api/products/{unsold}')
        self.check('D15', 'ENDED_UNSOLD' in json.dumps(public_unsold), 'unsold auction detail stays publicly readable')

        # Winner fulfilment reuses the existing trade confirmation.
        self.api('POST', f'/api/admin/intents/{listing[sold]["winnerIntentId"]}/success', token=self.seller)
        hist_b = self.data('GET', '/api/me/order-history', token=buyer_b)
        statuses_b = sorted(i['status'] for i in hist_b['items'])
        self.check('D16', statuses_b == ['FAILED', 'SUCCESS'],
                   f'winning bidder fulfilment succeeds through the existing success endpoint; the unrelated '
                   f'fixed-price intent that lost to buyer A is closed as FAILED (history: {statuses_b})')
        failed_intent = listing[failed]['winnerIntentId']
        self.api('POST', f'/api/admin/intents/{failed_intent}/fail', {'action': 'REQUEUE'}, self.seller, expected=409)
        self.api('POST', f'/api/admin/intents/{failed_intent}/fail', {'action': 'DISCARD'}, self.seller)
        hist_c = self.data('GET', '/api/me/order-history', token=buyer_c)
        self.check('D17', hist_c['total'] == 1 and hist_c['items'][0]['status'] == 'FAILED',
                   'failed auction fulfilment: REQUEUE refused (409), DISCARD leaves FAILED history')

        # Persistence: backend restart, then full container recreation; no duplicate reminders afterwards.
        before = {'snap': self.snapshot_state(ids), 'seller': len(s_alerts['items']),
                  'buyer_b': b_alerts['total'], 'hist_b': hist_b['total'], 'hist_c': hist_c['total']}
        self.compose('restart', 'backend')
        self.up()
        self.compose('down')
        self.up()
        time.sleep(12)  # at least two scheduler cycles after start-up
        self.seller = self.data('POST', '/api/admin/auth/login', {'username': 'admin', 'password': self.admin_password})['token']
        buyer_b2 = self.data('POST', '/api/auth/login', {'username': 'b_' + tag, 'password': self.customer_password})['token']
        after = {'snap': self.snapshot_state(ids),
                 'seller': len(self.data('GET', '/api/admin/auction-notifications?page=1&size=50', token=self.seller)['items']),
                 'buyer_b': self.data('GET', '/api/me/auction-notifications?page=1&size=20', token=buyer_b2)['total'],
                 'hist_b': self.data('GET', '/api/me/order-history', token=buyer_b2)['total'],
                 'hist_c': hist_c['total']}
        with urlopen(self.base + image.group(0), timeout=20) as r:
            persisted = r.read()
        self.check('D18', before == after and persisted == self.image_bytes,
                   'auctions, bids, reminders, history and uploaded image identical after backend restart and '
                   'container recreation; repeated scans created no duplicate reminders')

    def run(self):
        try:
            self.flow()
            self.report['result'] = 'PASS'
        except Exception as e:
            self.report['result'] = 'FAIL'
            self.report['error'] = type(e).__name__ + ': ' + str(e)
            raise
        finally:
            routes = sorted({r['method'] + ' ' + r['path'] for r in self.report['requests']})
            self.report['covered_endpoints'], self.report['endpoint_count'] = routes, len(routes)
            (self.output / 'docker-iteration2-results.json').write_text(
                json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
            if not self.keep:
                self.compose('down', '-v', '--remove-orphans', check=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keep', action='store_true', help='keep the isolated project running afterwards')
    args = parser.parse_args()
    Check(args.bundle, args.output, args.keep).run()
