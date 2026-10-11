"""Verify an offline Docker bundle in a new, isolated Compose project.

Only the randomly named project created here is started/stopped/removed.
Credentials stay in process environment and are never written to the report.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import struct
import time
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid
import zlib


class Check:
    def __init__(self, bundle: Path, output: Path, keep: bool, fixture: Path | None = None):
        self.bundle, self.output, self.keep = bundle.resolve(), output.resolve(), keep
        self.fixture = fixture
        self.output.mkdir(parents=True, exist_ok=True)
        self.project = 'oxstore-release-test-' + uuid.uuid4().hex[:12]
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]
        self.password = 'Ox!' + secrets.token_hex(16)
        self.new_password = 'New!' + secrets.token_hex(16)
        self.env = dict(os.environ, COMPOSE_PROJECT_NAME=self.project, APP_PORT=str(self.port),
                        APP_BIND_ADDRESS='127.0.0.1', DB_PASSWORD=secrets.token_hex(32),
                        JWT_SECRET=secrets.token_hex(32), TOKEN_LOOKUP_KEY=secrets.token_hex(32),
                        ADMIN_INITIAL_PASSWORD=self.password, OXSTORE_VERSION='0.1.0-docker.1')
        self.jwt = ''
        self.base = f'http://127.0.0.1:{self.port}'
        self.report = {'run_at': datetime.now().astimezone().isoformat(), 'project': self.project,
                       'scope': 'Real Compose / Nginx / Java17 / MySQL8 / persistent volumes', 'checks': []}

    def compose(self, *args, check=True, timeout=300):
        result = subprocess.run(['docker', 'compose', '-f', str(self.bundle / 'compose.yml'),
                                 '-p', self.project, *args], cwd=self.bundle, env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        text = result.stdout.decode('utf-8', errors='replace')
        # Compose operation logs contain no expanded environment or authentication response.
        with (self.output / 'compose-operations.log').open('a', encoding='utf-8') as log:
            log.write('docker compose ' + ' '.join(args) + '\n' + text + '\n')
        if check and result.returncode:
            raise RuntimeError(text[-2500:])
        return text

    def assert_check(self, name, condition, detail):
        self.report['checks'].append({'name': name, 'status': 'PASS' if condition else 'FAIL', 'detail': detail})
        print(('PASS ' if condition else 'FAIL ') + name + ': ' + detail, flush=True)
        if not condition:
            raise AssertionError(name)

    def api(self, method, path, data=None, admin=False, expected=200, raw=None, content_type=None):
        headers = {'Content-Type': content_type or 'application/json'}
        if admin:
            headers['Authorization'] = 'Bearer ' + self.jwt
        body = raw if raw is not None else (json.dumps(data, ensure_ascii=False).encode() if data is not None else None)
        try:
            with urlopen(Request(self.base + path, data=body, headers=headers, method=method), timeout=30) as r:
                status, payload = r.status, r.read()
        except HTTPError as e:
            status, payload = e.code, e.read()
        if status != expected:
            raise AssertionError(f'{method} request HTTP {status}, expected {expected}')
        value = json.loads(payload)
        if expected == 200 and value.get('code') != 0:
            raise AssertionError('Unexpected application response')
        return value.get('data')

    def login(self, password, expected=200):
        value = self.api('POST', '/api/admin/auth/login', {'username': 'admin', 'password': password}, expected=expected)
        if value:
            self.jwt = value['token']

    def publish(self, size=5 * 1024 * 1024, expected=200):
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')
        # Valid ancillary PNG chunk before IEND; padding after IEND is deliberately rejected by the application.
        payload = b'padding\0' + b'A' * (size - len(png) - 12 - 8)
        chunk = struct.pack('>I', len(payload)) + b'tEXt' + payload + struct.pack('>I', zlib.crc32(b'tEXt' + payload))
        image = png[:-12] + chunk + png[-12:]
        boundary = 'oxstore-' + uuid.uuid4().hex
        chunks = []
        for key, value in {'name': 'Docker交付验证商品', 'description': '真实容器发布、重排、历史和持久化验证', 'price': '19.90'}.items():
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="test.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + image + b'\r\n')
        chunks.append(f'--{boundary}--\r\n'.encode())
        return self.api('POST', '/api/admin/products', admin=True, raw=b''.join(chunks),
                        content_type='multipart/form-data; boundary=' + boundary, expected=expected)

    def queue(self):
        return self.api('GET', '/api/admin/intents', admin=True)

    def flow(self):
        self.compose('config', '-q')
        self.compose('up', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '240')
        state = [json.loads(line) for line in self.compose('ps', '--format', 'json').splitlines() if line.startswith('{')]
        self.assert_check('D01', len(state) == 3 and all(s.get('Health') == 'healthy' for s in state), 'three services healthy; no build or registry pull')
        self.assert_check('D02', all(not any(p.get('PublishedPort', 0) for p in s.get('Publishers') or [])
                                   for s in state if s['Service'] != 'frontend'), 'only frontend port is published')
        for path in ['/', '/admin/login', '/intent']:
            with urlopen(self.base + path, timeout=20) as r:
                body = r.read().decode()
                self.assert_check('D03' + path.replace('/', '_'), r.status == 200 and '<div id="root"></div>' in body, 'SPA route available through Nginx')
        self.assert_check('D04', self.api('GET', '/api/products/current') is None, 'new empty database serves no current product')
        self.api('GET', '/api/admin/intents', expected=401)
        self.assert_check('D05', True, 'unauthenticated admin request rejected through Nginx')
        self.login('invalid-password', expected=401)
        self.login(self.password)
        self.assert_check('D06', bool(self.jwt), 'seller login succeeds with generated initial password')
        self.publish(5 * 1024 * 1024 + 1, expected=400)
        self.assert_check('D07', True, 'image larger than 5 MiB rejected by application')
        product = self.publish()
        self.product_id = product['id']
        self.image_path = product['imagePath']
        with urlopen(self.base + self.image_path, timeout=20) as r:
            self.image_bytes = r.read()
        self.assert_check('D08', len(self.image_bytes) == 5 * 1024 * 1024, '5 MiB image passes Nginx, application and non-root upload volume')
        self.publish(size=100, expected=409)
        self.assert_check('D09', True, 'second active product rejected')
        self.api('POST', '/api/admin/products/current/freeze', admin=True)
        self.assert_check('D10', self.api('GET', '/api/products/current')['status'] == 'FROZEN', 'manual freeze visible to buyer')
        self.api('POST', '/api/intents', {'buyerName': '甲', 'buyerPhone': '13800000001'}, expected=409)
        self.api('POST', '/api/admin/products/current/unfreeze', admin=True)
        self.assert_check('D11', self.api('GET', '/api/products/current')['status'] == 'ONLINE', 'manual unfreeze restores product')
        self.api('POST', '/api/intents', {'buyerName': '长' * 21, 'buyerPhone': '13800000001'}, expected=400)
        self.api('POST', '/api/intents', {'buyerName': '甲', 'buyerPhone': '123'}, expected=400)
        self.assert_check('D12', True, 'name and phone boundary validation through Nginx')
        codes = [self.api('POST', '/api/intents', {'buyerName': name, 'buyerPhone': '1380000000' + str(i)})['code']
                 for i, name in enumerate(['甲', '乙', '丙'], 1)]
        a = self.api('GET', '/api/intents/' + codes[0])
        self.assert_check('D13', len(self.queue()) == 3 and a['position'] == 1, 'three anonymous buyers queue with private code lookup')
        self.api('PUT', '/api/intents/' + codes[0], {'buyerName': '甲修改'})
        self.api('DELETE', '/api/intents/' + codes[2])
        self.api('GET', '/api/intents/' + codes[2], expected=403)
        self.assert_check('D14', len(self.queue()) == 2, 'queued modification and cancellation work; cancelled code invalid')
        a = self.queue()[0]
        self.api('POST', f'/api/admin/intents/{a["id"]}/start', admin=True)
        active = next(i for i in self.queue() if i['status'] == 'IN_TRANSACTION')
        self.api('PUT', '/api/intents/' + codes[0], {'buyerName': '交易中修改'}, expected=409)
        self.api('POST', '/api/admin/products/current/unfreeze', admin=True, expected=409)
        self.assert_check('D15', bool(active['currentTradeAttemptId']), 'current trade attempt present; trade freeze cannot be manually released')
        self.api('POST', f'/api/admin/intents/{a["id"]}/fail', {'action': 'REQUEUE', 'tradeAttemptId': active['currentTradeAttemptId']}, admin=True)
        requeued = self.api('GET', '/api/intents/' + codes[0])
        q = self.queue()
        b = next(i for i in q if i['status'] == 'IN_TRANSACTION')
        self.assert_check('D16', requeued['position'] == 1 and b['id'] != a['id'] and requeued['submittedAt'] == a['submittedAt'], 'failure requeues to waiting tail; original code/time preserved; next buyer trades')
        self.api('POST', f'/api/admin/intents/{a["id"]}/success', {'tradeAttemptId': active['currentTradeAttemptId']}, admin=True, expected=409)
        self.assert_check('D17', True, 'stale trade confirmation rejected')
        self.api('POST', f'/api/admin/intents/{b["id"]}/success', {'tradeAttemptId': b['currentTradeAttemptId']}, admin=True)
        records = self.api('GET', f'/api/admin/products/{self.product_id}/records', admin=True)
        self.api('GET', '/api/intents/' + codes[0], expected=403)
        self.api('GET', '/api/intents/' + codes[1], expected=403)
        self.assert_check('D18', self.api('GET', '/api/products/current') is None and len(records['tradeAttempts']) == 2,
                          'successful sale unlists product, invalidates codes and keeps failed/successful attempts')
        history = self.api('GET', '/api/admin/products/history', admin=True)
        self.assert_check('D19', history['total'] == 1 and len(records['statusEvents']) >= 5, 'history list and state-event records available')
        self.api('PUT', '/api/admin/auth/password', {'oldPassword': self.password, 'newPassword': self.new_password}, admin=True)
        self.compose('restart', 'backend')
        self.compose('up', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '240')
        self.login(self.password, expected=401)
        self.login(self.new_password)
        self.assert_check('D20', self.api('GET', f'/api/admin/products/{self.product_id}/records', admin=True) == records, 'application restart retains changed password and complete records')
        self.compose('down')
        self.compose('up', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '240')
        self.login(self.new_password)
        with urlopen(self.base + self.image_path, timeout=20) as r:
            persisted_image = r.read()
        self.assert_check('D21', persisted_image == self.image_bytes and self.api('GET', f'/api/admin/products/{self.product_id}/records', admin=True) == records,
                          'container recreation retains database, images, password and history')

    def run(self):
        try:
            self.flow()
            self.report['result'] = 'PASS'
            if self.keep and self.fixture:
                self.fixture.write_text(json.dumps({'project': self.project, 'url': self.base,
                    'username': 'admin', 'password': self.new_password, 'env': {k: self.env[k] for k in
                        ['COMPOSE_PROJECT_NAME', 'APP_PORT', 'APP_BIND_ADDRESS', 'DB_PASSWORD', 'JWT_SECRET',
                         'TOKEN_LOOKUP_KEY', 'ADMIN_INITIAL_PASSWORD', 'OXSTORE_VERSION']}}), encoding='utf-8')
        except Exception as e:
            self.report['result'] = 'FAIL'
            self.report['error'] = type(e).__name__ + ': ' + str(e)
            raise
        finally:
            (self.output / 'docker-results.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
            if not self.keep:
                # Dedicated random project only; no existing user's containers or volumes.
                self.compose('down', '-v', '--remove-orphans', check=False)
        return self.report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keep', action='store_true', help='keep this isolated project running for additional verification')
    parser.add_argument('--ui-fixture', type=Path, help='temporary private fixture outside the public bundle, only with --keep')
    args = parser.parse_args()
    Check(args.bundle, args.output, args.keep, args.ui_fixture).run()
