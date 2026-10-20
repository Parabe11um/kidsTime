#!/usr/bin/env python3
"""Exercise shared Caddy routes and log privacy using disposable containers.

Images must already be loaded. No application, database, production network or
certificate volume is used. No ports are published to the host.
"""

import argparse
import json
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


BACKEND = r'''
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = os.environ['BACKEND_NAME'].encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Set-Cookie', 'probe=' + self.headers.get('X-Probe', ''))
        self.send_header('Location', self.path)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
'''

CLIENT = r'''
import http.client
import json
import sys

host, path, probe, token = sys.argv[1:]
connection = http.client.HTTPConnection('caddy-check-proxy', 80, timeout=3)
try:
    connection.request('GET', path, headers={
        'Host': host,
        'Authorization': 'Bearer ' + probe,
        'Cookie': 'session=' + probe,
        'Referer': 'https://' + host + '/room/' + token + '/',
        'X-Probe': probe,
    })
    response = connection.getresponse()
    result = {'status': response.status, 'headers': dict(response.getheaders()),
              'body': response.read().decode()}
except (OSError, http.client.HTTPException):
    result = {'status': 0, 'headers': {}, 'body': ''}
finally:
    connection.close()
print(json.dumps(result))
'''


def docker(*args):
    result = subprocess.run(
        ['docker', *args], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode:
        raise RuntimeError(f'Docker operation failed: {args[0]}\n{result.stderr}')
    return result.stdout.strip()


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Locally loaded Caddy image')
    parser.add_argument('--backend-image', required=True,
                        help='Locally loaded image with a Python 3 executable')
    args = parser.parse_args()
    for image in (args.image, args.backend_image):
        docker('image', 'inspect', image)

    root = Path(__file__).resolve().parents[1]
    prefix = 'kidstime-caddy-check-' + uuid.uuid4().hex
    networks = []
    containers = []
    probe = uuid.uuid4().hex
    token = str(uuid.uuid4())
    encoded = token.replace('-', '%2D')
    try:
        with tempfile.TemporaryDirectory(prefix=prefix) as directory:
            directory = Path(directory)
            extra = directory / 'extra'
            extra.mkdir()
            media = directory / 'media'
            media.mkdir()
            (media / 'probe.txt').write_text('MEDIA_OK')
            master = directory / 'Caddyfile'
            master.write_text((root / 'deploy/Caddyfile').read_text())
            mounts = [
                '-v', f'{master}:/etc/caddy/Caddyfile:ro',
                '-v', f'{extra}:/etc/caddy/extra:ro',
                '-v', f'{media}:/srv/media:ro',
                '-e', 'SITE_DOMAIN=http://kidstime.example.test',
            ]
            validate = [
                'run', '--rm', '--pull=never', '--network', 'none', *mounts,
                '--entrypoint', 'caddy', args.image, 'validate',
                '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile',
            ]
            docker(*validate)
            snippet = (root / 'deploy/score-it.caddy.example').read_text()
            snippet = snippet.replace('score-it.example.com',
                                      'http://score-it.example.test')
            (extra / 'score-it.caddy').write_text(snippet)
            docker(*validate)
            print('CADDY_CONFIG_OK')

            for suffix in ('kids', 'score'):
                network = prefix + '-' + suffix
                docker('network', 'create', '--internal', network)
                networks.append(network)
            for name, alias, network in (
                ('KIDSTIME_OK', 'kidstime-web', networks[0]),
                ('SCORE_IT_OK', 'score-it-web', networks[1]),
            ):
                container = docker(
                    'create', '--pull=never', '--name', prefix + '-' + alias,
                    '--network', network, '--network-alias', alias,
                    '-e', 'BACKEND_NAME=' + name, '--entrypoint', 'python',
                    args.backend_image, '-c', BACKEND,
                )
                containers.append(container)
                docker('start', container)

            caddy = docker(
                'create', '--pull=never', '--name', prefix + '-proxy',
                '--network', networks[0], '--network-alias', 'caddy-check-proxy',
                *mounts,
                '--entrypoint', 'caddy', args.image, 'run',
                '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile',
            )
            containers.append(caddy)
            docker('network', 'connect', networks[1], caddy)
            docker('start', caddy)
            info = json.loads(docker('inspect', caddy))[0]
            check(info['State']['Running'], 'Test proxy failed to start')
            check(not info['HostConfig'].get('PortBindings'), 'Test proxy publishes ports')

            def request(host, path):
                result = json.loads(docker(
                    'exec', containers[0], 'python', '-c', CLIENT,
                    host, path, probe, token,
                ))
                return result['status'], result['headers'], result['body'].encode()

            deadline = time.monotonic() + 20
            for host, expected in (
                ('kidstime.example.test', b'KIDSTIME_OK'),
                ('score-it.example.test', b'SCORE_IT_OK'),
            ):
                while True:
                    status, _, body = request(host, '/health/')
                    if status == 200 and body == expected:
                        break
                    check(time.monotonic() < deadline, 'Test proxy or upstream did not start')
                    time.sleep(0.2)

            for host, expected in (
                ('kidstime.example.test', b'KIDSTIME_OK'),
                ('score-it.example.test', b'SCORE_IT_OK'),
            ):
                for path in (
                    '/room/' + token + '/',
                    '/invite/' + encoded + '/?probe=' + probe,
                ):
                    status, headers, body = request(host, path)
                    check(status == 200 and body == expected, 'Upstream route changed')
                    if host == 'score-it.example.test':
                        check(headers.get('Referrer-Policy') == 'no-referrer',
                              'Score-it referrer policy is missing')
            status, _, body = request('kidstime.example.test', '/media/probe.txt')
            check(status == 200 and body == b'MEDIA_OK', 'KidsTime media route changed')
            print('CADDY_ROUTES_OK')

            docker('stop', '--time', '2', containers[1])
            status, _, _ = request('score-it.example.test', '/room/' + token + '/')
            check(status == 502, 'Proxy error control did not return 502')
            deadline = time.monotonic() + 5
            while True:
                # docker logs emits access logs to stdout and runtime errors to stderr.
                result = subprocess.run(
                    ['docker', 'logs', caddy], stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, check=True, timeout=10,
                )
                logs = result.stdout + result.stderr
                records = []
                for line in logs.splitlines():
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                accesses = [r for r in records
                            if r.get('logger', '').startswith('http.log.access')]
                errors = [r for r in records if r.get('logger') == 'http.log.error']
                if len(accesses) >= 7 and errors:
                    break
                check(time.monotonic() < deadline, 'Access/error log controls are absent')
                time.sleep(0.1)
            for secret in (probe, token, encoded):
                check(secret.lower() not in logs.lower(), 'Synthetic token leaked to Caddy logs')
            check({r.get('request', {}).get('host') for r in accesses}
                  == {'kidstime.example.test', 'score-it.example.test'},
                  'Access log control does not cover both sites')
            for record in accesses + errors:
                req = record.get('request', {})
                check(req.get('uri') == '[redacted]', 'Logged request URI is not redacted')
                check('headers' not in req, 'Request headers are still logged')
                check('resp_headers' not in record, 'Response headers are still logged')
            print('CADDY_ACCESS_LOG_PRIVACY_OK')
            print('CADDY_ERROR_LOG_PRIVACY_OK')
            print('CADDY_SECURITY_OK')
    finally:
        for container in reversed(containers):
            subprocess.run(['docker', 'rm', '-fv', container],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
        for network in reversed(networks):
            subprocess.run(['docker', 'network', 'rm', network],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=30)


if __name__ == '__main__':
    main()
