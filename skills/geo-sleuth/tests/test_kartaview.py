# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10"]
# ///
"""Offline contract tests; no provider requests or model imports."""
import importlib.util
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'kartaview.py'


class NearbyTest(unittest.TestCase):
    def test_one_response_dedup_and_uncertainty(self):
        self.assertTrue(SCRIPT.exists(), 'bounded adapter is not implemented')
        spec = importlib.util.spec_from_file_location('kartaview', SCRIPT)
        assert spec is not None and spec.loader is not None
        kv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(kv)
        row = {'id': '123', 'lat': '-6.19', 'lng': '106.84',
               'matchLat': '-6.1901', 'matchLng': '106.8401',
               'shotDate': '2020-04-07 10:42:08.000', 'sequenceId': '12',
               'sequenceIndex': '3', 'projection': 'PLANE', 'gpsAccuracy': '3.9',
               'autoImgProcessingStatus': 'FINISHED', 'autoImgProcessingResult': 'BLURRED',
               'fileurlProc': 'https://storage13.openstreetcam.org/files/photo/2020/4/7/proc/x.jpg'}
        envelope = {'status': {'apiCode': 600, 'httpCode': 200},
                    'result': {'data': [row, row], 'hasMoreData': True}}
        calls = []
        def transport(url, cap, kind):
            calls.append(url)
            return json.dumps(envelope).encode()
        result = kv.nearby((-6.1939, 106.8494), 15, transport)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], 'https://api.kartaview.org/2.0/photo/?lat=-6.1939&lng=106.8494&zoomLevel=15')
        self.assertEqual((result['returned_count'], result['count'], result['duplicate_count']), (2, 1, 1))
        self.assertEqual((result['coverage'], result['status'], result['has_more']), ('bounded/unknown', 'partial', True))
        item = result['items'][0]
        self.assertNotEqual(item['wgs'], item['matched_wgs'])
        self.assertEqual(item['capture_time']['timezone'], 'unknown')
        self.assertEqual(item['capture_time']['raw'], row['shotDate'])
        self.assertEqual(item['sequence_id'], '12')
        self.assertEqual(item['gps_accuracy_m'], 3.9)
        self.assertEqual(item['projection'], 'PLANE')
        self.assertNotIn('heading', item)
        self.assertEqual(item['attribution'], '© Grab and KartaView Contributors')


class FetchTest(unittest.TestCase):
    def test_cli_fetch_one_decoded_thumbnail_fresh_directory(self):
        import io
        from PIL import Image
        spec = importlib.util.spec_from_file_location('kartaview', SCRIPT)
        assert spec and spec.loader
        kv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(kv)
        image = io.BytesIO()
        Image.new('RGB', (16, 12), 'blue').save(image, format='JPEG')
        row = {'id': '123', 'thumbnail_url': 'https://storage13.openstreetcam.org/files/photo/2020/4/7/th/x.jpg',
               'autoImgProcessingStatus': 'FINISHED', 'autoImgProcessingResult': 'BLURRED'}
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as root:
            source, out = Path(root) / 'nearby.json', Path(root) / 'images'
            source.write_text(json.dumps({'provider': 'KartaView', 'items': [row]}))
            calls = []
            def transport(url, cap, kind):
                calls.append(url)
                return image.getvalue()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(kv.main(['fetch', '--metadata', str(source), '--id', '123', '--out-dir', str(out)], transport), 0)
            self.assertEqual(len(calls), 1)
            index = json.loads((out / 'index.json').read_text())
            self.assertEqual(set(index), {'123'})
            with Image.open(index['123']) as im:
                im.load()
                self.assertEqual(im.size, (16, 12))
            report = json.loads((out / 'fetch.json').read_text())
            self.assertEqual(report['count'], 1)
            self.assertEqual(report['failure_count'], 0)
            saved = Path(index['123']).read_bytes()
            self.assertEqual(saved, image.getvalue())
            self.assertEqual(report['response_sha256'], hashlib.sha256(saved).hexdigest())
            self.assertEqual(report['source_url'], row['thumbnail_url'])
            self.assertEqual(report['index'], index)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(kv.main(['fetch', '--metadata', str(source), '--id', '123', '--out-dir', str(out)], transport), 1)
            self.assertEqual(len(calls), 1)


def load_adapter():
    spec = importlib.util.spec_from_file_location('kartaview', SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    return {'status': {'apiCode': 600, 'httpCode': 200}, 'result': {'hasMoreData': False,
            'data': [{'id': '1', 'lat': '-6.19', 'lng': '106.84'}]}}


class FaultTest(unittest.TestCase):
    def setUp(self):
        self.kv = load_adapter()

    def test_envelope_faults_not_empty_success(self):
        for payload in [None, [], {}, {'status': []},
                        {'status': {'apiCode': '600', 'httpCode': 200}},
                        {'status': {'apiCode': 601, 'httpCode': 200}},
                        {'status': {'apiCode': 600, 'httpCode': 200}, 'result': {'data': [], 'hasMoreData': 'false'}},
                        {'status': {'apiCode': 600, 'httpCode': 200}, 'result': {'data': {}}}]:
            with self.subTest(payload=payload), self.assertRaises(self.kv.AdapterError):
                self.kv.nearby((0, 0), 15, lambda *args: json.dumps(payload).encode())
        for body in [b'<html>no</html>', b'{', b'\xff']:
            with self.subTest(body=body), self.assertRaises(self.kv.AdapterError):
                self.kv.nearby((0, 0), 15, lambda *args: body)

    def test_bad_rows_retained_and_counts_reconcile(self):
        for key, value in [('lat', 'NaN'), ('lat', 91), ('lng', '-inf'), ('lng', True),
                           ('matchLat', '2'), ('gpsAccuracy', -1), ('sequenceId', '../x'),
                           ('projection', {}), ('shotDate', 'not a date'), ('id', False)]:
            payload = fixture()
            payload['result']['data'][0][key] = value
            with self.subTest(key=key, value=value):
                out = self.kv.nearby((0, 0), 15, lambda *args: json.dumps(payload).encode())
                self.assertEqual((out['count'], out['failure_count'], out['returned_count']), (0, 1, 1))
                self.assertEqual(out['status'], 'partial')
                self.assertNotEqual(out['status'], 'success_empty')

    def test_empty_and_no_more_never_census(self):
        payload = fixture()
        payload['result']['data'] = []
        out = self.kv.nearby((0, 0), 15, lambda *args: json.dumps(payload).encode())
        self.assertEqual((out['status'], out['coverage'], out['has_more']), ('success_empty', 'bounded/unknown', False))
        payload['result']['data'] = [{'id': 1, 'lat': 0, 'lng': 0, 'shotDate': '2020-01-01T12:00:00+07:00'}]
        out = self.kv.nearby((0, 0), 15, lambda *args: json.dumps(payload).encode())
        self.assertEqual(out['status'], 'success_unknown_coverage')
        self.assertEqual(out['items'][0]['capture_time']['timezone'], 'explicit_offset')

    def test_numeric_overflow_is_a_row_failure(self):
        for key in ('lat', 'lng', 'matchLat', 'gpsAccuracy'):
            payload = fixture()
            payload['result']['data'][0][key] = 10**400
            with self.subTest(key=key):
                out = self.kv.nearby((0, 0), 15, lambda *args: json.dumps(payload).encode())
                self.assertEqual((out['count'], out['failure_count'], out['status']), (0, 1, 'partial'))
                self.assertEqual(out['failures'][0]['category'], 'schema')

    def test_invalid_first_duplicate_does_not_hide_valid_photo(self):
        payload = fixture()
        valid = payload['result']['data'][0].copy()
        payload['result']['data'][0]['lat'] = 'invalid'
        payload['result']['data'].extend([valid, valid])
        out = self.kv.nearby((0, 0), 15, lambda *args: json.dumps(payload).encode())
        self.assertEqual((out['count'], out['failure_count'], out['duplicate_count'], out['returned_count']),
                         (1, 1, 1, 3))
        self.assertEqual(out['items'][0]['id'], '1')

    def test_deep_json_is_clean_cli_failure_without_output(self):
        body = '[' * 100_000 + '0' + ']' * 100_000
        calls = []
        def transport(*args):
            calls.append(args)
            return body.encode()
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as root:
            source, out = Path(root) / 'near.json', Path(root) / 'images'
            source.write_text(body)
            commands = [
                ['nearby', '--at', '0,0', '--out', str(out)],
                ['fetch', '--metadata', str(source), '--id', '1', '--out-dir', str(out)],
            ]
            for command in commands:
                with self.subTest(command=command[0]), contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(self.kv.main(command, transport), 1)
                failure = json.loads(err.getvalue())
                self.assertEqual((failure['status'], failure['category']), ('failed', 'schema'))
                self.assertFalse(out.exists())
            self.assertEqual(len(calls), 1)

    def test_invalid_cli_inputs_and_overwrite_make_zero_requests(self):
        calls = []
        def transport(*args):
            calls.append(args)
            return json.dumps(fixture()).encode()
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as root:
            out = Path(root) / 'out.json'
            for at in ['nan,1', '91,1', '1,inf', 'bad', '1,2,3']:
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(self.kv.main(['nearby', '--at', at, '--out', str(out)], transport), 1)
                self.assertFalse(out.exists())
            out.write_text('preserve')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.kv.main(['nearby', '--at', '0,0', '--out', str(out)], transport), 1)
            self.assertEqual(out.read_text(), 'preserve')
            self.assertEqual(calls, [])
        for zoom in [0, 13, 20, True, 15.0]:
            with self.assertRaises(self.kv.AdapterError):
                self.kv.nearby((0, 0), zoom, transport)
        self.assertEqual(calls, [])

    def test_public_cli_nearby_offline_fixture(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as root:
            out = Path(root) / 'out.json'
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                rc = self.kv.main(['nearby', '--at', '0,0', '--zoom', '15', '--out', str(out)],
                                  lambda *args: json.dumps(fixture()).encode())
            self.assertEqual(rc, 0)
            data = json.loads(out.read_text())
            self.assertEqual(data['count'], len(data['items']))
            self.assertEqual(json.loads(captured.getvalue())['count'], 1)
        process = subprocess.run([sys.executable, str(SCRIPT), '--help'], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0)
        self.assertIn('fetch', process.stdout)

    def test_unsafe_asset_urls_never_exposed(self):
        good = 'https://storage13.openstreetcam.org/files/photo/2020/4/7/proc/x.jpg'
        for url in [good.replace('https:', 'http:'), good + '?token=SECRET',
                    good.replace('storage13.openstreetcam.org', 'evil.example'),
                    good.replace('/proc/', '/raw/'), good.replace('/proc/', '/../proc/'),
                    'https://storage13.openstreetcam.org@evil.example/x', 'https://[broken']:
            row = fixture()['result']['data'][0]
            row.update(autoImgProcessingStatus='FINISHED', autoImgProcessingResult='BLURRED', fileurlProc=url)
            with self.subTest(url=url):
                self.assertIsNone(self.kv.normalize(row)['processed_url'])
        row['fileurlProc'] = good
        row['autoImgProcessingResult'] = 'UNKNOWN'
        self.assertIsNone(self.kv.normalize(row)['processed_url'])

    def test_fetch_failures_write_report_no_image(self):
        for fault in ['decode', 'size', 'policy', 'transport']:
            row = {'id': '123', 'thumbnail_url': 'https://storage13.openstreetcam.org/files/photo/2020/4/7/th/x.jpg',
                   'autoImgProcessingStatus': 'FINISHED', 'autoImgProcessingResult': 'BLURRED'}
            if fault == 'policy':
                row['thumbnail_url'] = 'https://evil.example/raw.jpg?token=SECRET'
            def transport(*args):
                if fault == 'transport':
                    raise self.kv.AdapterError('transport', 'timeout')
                return b'x' * (4 * 1024 * 1024 + 1) if fault == 'size' else b'not image'
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as root:
                source, out = Path(root) / 'near.json', Path(root) / 'images'
                source.write_text(json.dumps({'provider': 'KartaView', 'items': [row]}))
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(self.kv.main(['fetch', '--metadata', str(source), '--id', '123', '--out-dir', str(out)], transport), 1)
                report = json.loads((out / 'fetch.json').read_text())
                self.assertEqual(report['failures'][0]['category'], fault)
                self.assertEqual(report['count'], 0)
                self.assertEqual(json.loads((out / 'index.json').read_text()), {})
                self.assertNotIn('SECRET', (out / 'fetch.json').read_text())
                self.assertEqual(len(list(out.iterdir())), 2)

    def test_missing_pillow_is_a_clean_dependency_failure(self):
        real_import = __import__
        def no_pillow(name, *args, **kwargs):
            if name == 'PIL':
                raise ImportError('missing Pillow')
            return real_import(name, *args, **kwargs)
        with mock.patch('builtins.__import__', side_effect=no_pillow):
            with self.assertRaises(self.kv.AdapterError) as caught:
                self.kv.fetch('unused.json', '1', 'unused')
            self.assertEqual(caught.exception.category, 'dependency')

    def test_incomplete_network_read_is_clean_failure(self):
        import http.client
        response = mock.MagicMock()
        response.headers.get_content_type.return_value = 'application/json'
        response.read.side_effect = http.client.IncompleteRead(b'{', 10)
        with mock.patch.object(self.kv.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value = response
            with self.assertRaises(self.kv.AdapterError) as caught:
                self.kv.request_bytes('https://example.invalid', 20, 'json')
            self.assertEqual(caught.exception.category, 'transport')

    def test_http_policy_byte_budget_and_no_redirect(self):
        import urllib.error
        from email.message import Message
        for code, category in [(301, 'http'), (403, 'http'), (429, 'rate_limited'), (500, 'http')]:
            error = urllib.error.HTTPError('https://example.invalid', code, 'no', Message(), None)
            with mock.patch.object(self.kv.urllib.request, 'build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(self.kv.AdapterError) as caught:
                    self.kv.request_bytes('https://example.invalid', 10, 'json')
                self.assertEqual(caught.exception.category, category)
                self.assertEqual(opener.return_value.open.call_count, 1)
        self.assertIsNone(self.kv.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.example'))
        for content_type, data, category in [('text/html', b'no', 'content_type'), ('application/json', b'123456', 'size')]:
            response = mock.MagicMock()
            response.headers.get_content_type.return_value = content_type
            response.read.return_value = data
            with mock.patch.object(self.kv.urllib.request, 'build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value = response
                with self.assertRaises(self.kv.AdapterError) as caught:
                    self.kv.request_bytes('https://example.invalid', 5, 'json')
                self.assertEqual(caught.exception.category, category)


if __name__ == '__main__':
    unittest.main()
