"""The HTTP API (JSON under /v1). Standard library only.

Every response is a JSON object. Errors are
    {"error": {"code": "<stable code>", "message": "<sentence for people>"}}
with the HTTP status that fits (400 bad input, 401 no or wrong key, 403 this
deployment does not issue, 404 not found, 405 wrong method, 409 conflict,
410 retired, 422 understood but refused, 429 daily limit, 500 server fault).
"""
import json
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from .service import ApiError

MAX_BODY = 64 * 1024


def _float(qs, name):
    v = qs.get(name)
    if v is None or v == '':
        return None
    try:
        return float(v)
    except ValueError:
        raise ApiError(400, 'bad_number', '%s must be a number.' % name)


def _int(qs, name):
    v = qs.get(name)
    if v is None or v == '':
        return None
    try:
        return int(v)
    except ValueError:
        raise ApiError(400, 'bad_number', '%s must be a whole number.' % name)


def routes(svc):
    """(method, pattern, handler(match, query, body, key)) in matching order."""
    return [
        ('GET', r'/v1/health', lambda m, q, b, k: (200, svc.health())),
        ('GET', r'/v1/info', lambda m, q, b, k: (200, svc.info())),
        ('GET', r'/v1/find', lambda m, q, b, k: (200, svc.find(q.get('q')))),
        ('GET', r'/v1/at', lambda m, q, b, k: (200, svc.at(_float(q, 'lat'), _float(q, 'lng')))),
        ('GET', r'/v1/near', lambda m, q, b, k: (200, svc.near(_float(q, 'lat'), _float(q, 'lng'), _float(q, 'radius'), _int(q, 'limit')))),
        ('GET', r'/v1/verify', lambda m, q, b, k: (200, _verify(svc, q))),
        ('GET', r'/v1/spot', lambda m, q, b, k: (200, svc.spot(_float(q, 'lat'), _float(q, 'lng')))),
        ('GET', r'/v1/spot/decode', lambda m, q, b, k: (200, svc.spot_decode(q.get('code')))),
        ('GET', r'/v1/zones', lambda m, q, b, k: (200, svc.zones())),
        ('GET', r'/v1/zones/([^/]+)', lambda m, q, b, k: (200, svc.zone(m.group(1)))),
        ('GET', r'/v1/zones/([^/]+)/codes', lambda m, q, b, k: (200, svc.zone_codes(m.group(1), q.get('after'), _int(q, 'limit')))),
        ('GET', r'/v1/areas', lambda m, q, b, k: (200, svc.areas_by_name(q.get('name')))),
        ('GET', r'/v1/areas/([^/]+)', lambda m, q, b, k: (200, svc.area(m.group(1)))),
        ('GET', r'/v1/codes/([^/]+)', lambda m, q, b, k: (200, svc.get(m.group(1)))),
        ('POST', r'/v1/codes', lambda m, q, b, k: (201, svc.issue(k, b))),
        ('PATCH', r'/v1/codes/([^/]+)', lambda m, q, b, k: (200, svc.change(k, m.group(1), b))),
    ]


def _verify(svc, q):
    code = q.get('code')
    if not code:
        raise ApiError(400, 'missing_code', 'Give code: a machine form such as CI-010114-083-6136-2.')
    return svc.verify(code)


def make_handler(svc, cors_origins=(), log_requests=True):
    table = [(meth, re.compile('^' + pat + '$'), fn) for meth, pat, fn in routes(svc)]
    origins = set(cors_origins)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'N-Ways-Addressing-CI'
        sys_version = ''
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            if log_requests:
                sys.stderr.write('%s %s\n' % (self.log_date_time_string(), fmt % args))

        def _cors(self):
            origin = self.headers.get('Origin')
            if origin and ('*' in origins or origin in origins):
                self.send_header('Access-Control-Allow-Origin', '*' if '*' in origins else origin)
                self.send_header('Vary', 'Origin')

        def _send(self, status, obj):
            body = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store' if self.command != 'GET' or status >= 400 else 'public, max-age=60')
            self._cors()
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def _error(self, status, code, message, extra=None):
            err = {'code': code, 'message': message}
            if extra:
                err.update(extra)
            self._send(status, {'error': err})

        def _dispatch(self, method):
            try:
                url = urlsplit(self.path)
                path = unquote(url.path).rstrip('/') or '/'
                q = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
                allowed = []
                for meth, rx, fn in table:
                    m = rx.match(path)
                    if not m:
                        continue
                    if meth != method and not (method == 'HEAD' and meth == 'GET'):
                        allowed.append(meth)
                        continue
                    body = None
                    if method in ('POST', 'PATCH'):
                        body = self._body()
                    auth = self.headers.get('Authorization', '')
                    key = auth[7:].strip() if auth.lower().startswith('bearer ') else None
                    status, out = fn(m, q, body, key)
                    return self._send(status, out)
                if allowed:
                    return self._error(405, 'method_not_allowed', '%s is not allowed here; use %s.' % (method, ', '.join(sorted(set(allowed)))))
                return self._error(404, 'no_such_endpoint', 'No endpoint %s. See /v1/info and server/openapi.yaml.' % path)
            except ApiError as e:
                return self._error(e.status, e.code, e.message, e.extra)
            except Exception:
                traceback.print_exc()
                return self._error(500, 'server_error', 'The server failed to answer; the fault is logged.')
            finally:
                svc.store.release()

        def _body(self):
            try:
                n = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                raise ApiError(400, 'bad_body', 'Content-Length is not a number.')
            if n > MAX_BODY:
                raise ApiError(400, 'body_too_large', 'The body is at most 64 KB.')
            raw = self.rfile.read(n) if n else b''
            try:
                return json.loads(raw.decode('utf-8') or 'null')
            except (UnicodeDecodeError, ValueError):
                raise ApiError(400, 'bad_json', 'The body is not valid JSON.')

        def do_GET(self):
            self._dispatch('GET')

        def do_HEAD(self):
            self._dispatch('HEAD')

        def do_POST(self):
            self._dispatch('POST')

        def do_PATCH(self):
            self._dispatch('PATCH')

        def do_PUT(self):
            self._dispatch('PUT')

        def do_DELETE(self):
            self._dispatch('DELETE')

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            self.send_header('Access-Control-Max-Age', '600')
            self.send_header('Content-Length', '0')
            self.end_headers()

    return Handler


def serve(svc, host, port, cors_origins=(), log_requests=True):
    httpd = ThreadingHTTPServer((host, port), make_handler(svc, cors_origins, log_requests))
    httpd.daemon_threads = True
    return httpd
