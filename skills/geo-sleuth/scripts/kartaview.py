#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10"]
# ///
"""One public KartaView metadata response; never a coverage census."""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = 'https://api.kartaview.org/2.0/photo/'
ATTRIBUTION = '© Grab and KartaView Contributors'
LICENSE = 'https://creativecommons.org/licenses/by-sa/4.0/'
METADATA_CAP = 4 * 1024 * 1024


class AdapterError(Exception):
    def __init__(self, category, message):
        self.category = category
        super().__init__(message)


def number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise AdapterError('schema', f'{label}: expected number')
    try:
        n = float(value)
    except (ValueError, OverflowError):
        raise AdapterError('schema', f'{label}: invalid number') from None
    if not math.isfinite(n) or not low <= n <= high:
        raise AdapterError('schema', f'{label}: out of range/nonfinite')
    return n


def identifier(value, label='id'):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r'[0-9]{1,30}', str(value)):
        raise AdapterError('schema', f'{label}: expected decimal identifier')
    return str(value)


def asset_url(value, variant):
    """Narrow allowlist from retained provider response; no signed/unknown URLs."""
    if not isinstance(value, str):
        return None
    try:
        p = urllib.parse.urlsplit(value)
    except ValueError:
        return None
    if (p.scheme != 'https' or p.netloc != 'storage13.openstreetcam.org'
            or p.query or p.fragment or not re.fullmatch(
                rf'/files/photo/[0-9]{{4}}/[0-9]{{1,2}}/[0-9]{{1,2}}/{variant}/[A-Za-z0-9_-]+\.jpg', p.path)):
        return None
    return value


def normalize(row):
    if not isinstance(row, dict):
        raise AdapterError('schema', 'photo: expected object')
    item = {'id': identifier(row.get('id')),
            'wgs': [number(row.get('lat'), -90, 90, 'lat'), number(row.get('lng'), -180, 180, 'lng')],
            'matched_wgs': None, 'license': LICENSE, 'attribution': ATTRIBUTION}
    if row.get('matchLat') is not None or row.get('matchLng') is not None:
        item['matched_wgs'] = [number(row.get('matchLat'), -90, 90, 'matchLat'),
                               number(row.get('matchLng'), -180, 180, 'matchLng')]
    for source, target in [('sequenceId', 'sequence_id'), ('sequenceIndex', 'sequence_index')]:
        item[target] = identifier(row[source], source) if row.get(source) is not None else None
    item['gps_accuracy_m'] = number(row['gpsAccuracy'], 0, 1e9, 'gpsAccuracy') if row.get('gpsAccuracy') is not None else None
    raw = row.get('shotDate')
    capture = {'raw': raw, 'timezone': 'unknown'}
    if raw is not None:
        if not isinstance(raw, str):
            raise AdapterError('schema', 'shotDate: expected string/null')
        try:
            date = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            raise AdapterError('schema', 'shotDate: invalid date') from None
        if date.tzinfo is not None:
            capture['timezone'] = 'explicit_offset'
    item['capture_time'] = capture
    for key in ('projection', 'imagePartProjection', 'autoImgProcessingStatus', 'autoImgProcessingResult'):
        value = row.get(key)
        if value is not None and not isinstance(value, str):
            raise AdapterError('schema', f'{key}: expected string/null')
        item[key] = value
    safe = row.get('autoImgProcessingStatus') == 'FINISHED' and row.get('autoImgProcessingResult') == 'BLURRED'
    item['processed_url'] = asset_url(row.get('fileurlProc'), 'proc') if safe else None
    item['thumbnail_url'] = asset_url(row.get('fileurlTh'), 'th') if safe else None
    # No raw URL, camera parameters, heading, or inferred calibrated pose.
    return item


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_bytes(url, cap, kind):
    request = urllib.request.Request(url, headers={'User-Agent': 'geo-sleuth-kartaview/1.0',
                                                  'Accept': 'application/json' if kind == 'json' else 'image/jpeg'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            content_type = response.headers.get_content_type()
            if (kind == 'json' and content_type != 'application/json') or (kind == 'image' and content_type not in ('image/jpeg', 'image/png')):
                raise AdapterError('content_type', 'unexpected response content type')
            data = response.read(cap + 1)
    except urllib.error.HTTPError as exc:
        category = 'rate_limited' if exc.code == 429 else 'http'
        raise AdapterError(category, f'HTTP {exc.code}; no retry or redirect') from None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
        raise AdapterError('transport', 'public read failed (DNS/TLS/timeout/network)') from None
    if len(data) > cap:
        raise AdapterError('size', 'response exceeds byte budget')
    return data


def nearby(at, zoom, transport=request_bytes):
    lat = number(at[0], -90, 90, 'latitude')
    lon = number(at[1], -180, 180, 'longitude')
    if isinstance(zoom, bool) or not isinstance(zoom, int) or not 14 <= zoom <= 19:
        raise AdapterError('input', 'zoom must be an integer from 14 to 19 (local budget policy)')
    url = ENDPOINT + '?' + urllib.parse.urlencode({'lat': lat, 'lng': lon, 'zoomLevel': zoom})
    data = transport(url, METADATA_CAP, 'json')
    if len(data) > METADATA_CAP:
        raise AdapterError('size', 'metadata exceeds byte budget')
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        raise AdapterError('schema', 'invalid JSON metadata') from None
    if not isinstance(payload, dict) or not isinstance(payload.get('status'), dict):
        raise AdapterError('schema', 'missing status envelope')
    status = payload['status']
    if type(status.get('apiCode')) is not int or type(status.get('httpCode')) is not int:
        raise AdapterError('schema', 'invalid API status types')
    if status['apiCode'] != 600 or status['httpCode'] != 200:
        raise AdapterError('api', f"API code {status['apiCode']}, HTTP envelope {status['httpCode']}")
    result = payload.get('result')
    if (not isinstance(result, dict) or not isinstance(result.get('data'), list)
            or type(result.get('hasMoreData')) is not bool):
        raise AdapterError('schema', 'expected result.data array and boolean hasMoreData')
    items, failures, seen = [], [], set()
    duplicates = 0
    for index, row in enumerate(result['data']):
        try:
            pid = identifier(row.get('id')) if isinstance(row, dict) else identifier(None)
            if pid in seen:
                duplicates += 1
                continue
            items.append(normalize(row))
            seen.add(pid)
        except AdapterError as exc:
            failures.append({'row': index, 'category': exc.category, 'error': str(exc)})
    more = result['hasMoreData']
    return {'schema_version': 1, 'provider': 'KartaView', 'query_url': url,
            'query': {'at': [lat, lon], 'zoom': zoom}, 'coverage': 'bounded/unknown',
            'status': 'partial' if more or failures else ('success_empty' if not items else 'success_unknown_coverage'),
            'has_more': more, 'metadata_requests': 1, 'returned_count': len(result['data']),
            'count': len(items), 'duplicate_count': duplicates, 'failure_count': len(failures),
            'items': items, 'failures': failures, 'license': LICENSE, 'attribution': ATTRIBUTION,
            'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'response_sha256': hashlib.sha256(data).hexdigest()}


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as out:
        json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write('\n')


def fetch(metadata, pid, directory, transport=request_bytes):
    """Fetch exactly one explicitly selected blurred thumbnail into a new directory."""
    import io
    import warnings
    try:
        from PIL import Image
    except ImportError:
        raise AdapterError('dependency', 'fetch needs Pillow; run with uv run scripts/kartaview.py') from None

    pid = identifier(pid)
    source = Path(metadata)
    if source.stat().st_size > METADATA_CAP * 3:
        raise AdapterError('size', 'local metadata exceeds budget')
    try:
        payload = json.loads(source.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError, RecursionError):
        raise AdapterError('schema', 'invalid local metadata JSON') from None
    if (not isinstance(payload, dict) or payload.get('provider') != 'KartaView'
            or not isinstance(payload.get('items'), list)):
        raise AdapterError('schema', 'not a KartaView adapter metadata file')
    selected = [row for row in payload['items'] if isinstance(row, dict) and row.get('id') == pid]
    if len(selected) != 1:
        raise AdapterError('input', 'id must select exactly one metadata item')
    destination = Path(directory).absolute()
    destination.mkdir()  # exist_ok=False: no existing directory, even if empty
    row = selected[0]
    report = {'id': pid, 'count': 0, 'failure_count': 0, 'failures': [],
              'attribution': ATTRIBUTION, 'license': LICENSE, 'index': {},
              'source_metadata': str(source.absolute()), 'image_requests': 0}
    try:
        url = asset_url(row.get('thumbnail_url'), 'th')
        if (not url or row.get('autoImgProcessingStatus') != 'FINISHED'
                or row.get('autoImgProcessingResult') != 'BLURRED'):
            raise AdapterError('policy', 'no allowlisted, finished/blurred thumbnail; no raw fallback')
        report['image_requests'] = 1
        data = transport(url, 4 * 1024 * 1024, 'image')
        if len(data) > 4 * 1024 * 1024:
            raise AdapterError('size', 'thumbnail exceeds 4 MiB')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format not in ('JPEG', 'PNG') or image.width * image.height > 4_000_000:
                        raise AdapterError('size', 'thumbnail format/pixel budget exceeded')
                    image.load()  # prove full decode, not just a JPEG header
                    report['dimensions'] = [image.width, image.height]
        except AdapterError:
            raise
        except Exception:
            raise AdapterError('decode', 'thumbnail is not a safely decodable JPEG/PNG') from None
        target = destination / (pid + '.jpg' if data.startswith(b'\xff\xd8') else pid + '.png')
        with target.open('xb') as out:
            out.write(data)
        report.update(count=1, source_url=url, response_sha256=hashlib.sha256(data).hexdigest())
        report['index'][pid] = str(target)
    except AdapterError as exc:
        report['failure_count'] = 1
        report['failures'].append({'id': pid, 'category': exc.category, 'error': str(exc)})
    write_new(destination / 'index.json', report['index'])
    write_new(destination / 'fetch.json', report)
    return report


def main(argv=None, transport=request_bytes):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    near = sub.add_parser('nearby', help='one public metadata request; no pagination')
    near.add_argument('--at', required=True, help='WGS84 lat,lon; for negative latitude use --at=-6.19,106.84')
    near.add_argument('--zoom', type=int, choices=range(14, 20), default=15)
    near.add_argument('--out', required=True)
    thumbnail = sub.add_parser('fetch', help='one explicit blurred thumbnail; new output directory only')
    thumbnail.add_argument('--metadata', required=True)
    thumbnail.add_argument('--id', required=True)
    thumbnail.add_argument('--out-dir', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'fetch':
            report = fetch(args.metadata, args.id, args.out_dir, transport)
            print(json.dumps({key: report[key] for key in ('id', 'count', 'failure_count', 'failures', 'image_requests')}))
            return 1 if report['failure_count'] else 0
        if Path(args.out).exists() or Path(args.out).is_symlink():
            raise AdapterError('output', 'output exists; refusing overwrite')
        parts = args.at.split(',')
        if len(parts) != 2:
            raise AdapterError('input', '--at needs lat,lon')
        result = nearby(parts, args.zoom, transport)
        write_new(args.out, result)
        print(json.dumps({key: result[key] for key in ('status', 'count', 'returned_count', 'duplicate_count', 'failure_count', 'coverage', 'has_more')}))
        return 0
    except (AdapterError, OSError) as exc:
        print(json.dumps({'status': 'failed', 'category': getattr(exc, 'category', 'output'),
                          'error': str(exc), 'coverage': 'bounded/unknown'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
