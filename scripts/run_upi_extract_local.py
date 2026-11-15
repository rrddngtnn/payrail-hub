from __future__ import annotations
import argparse
import json
import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'api_python'))
from rail_specs import SPECS, get_spec
from upi_link_service import extract_upi_link, resolve_rail_proxy, resolve_upi_access_token


def _mask_proxy_url(proxy: str) -> str:
    """Mask credentials in a proxy URL. Handles scheme and scheme-less forms."""
    import re as _re
    return _re.sub(r'(?i)(^[a-z][a-z0-9+.-]*://)?[^/@:]+:[^/@]+@', lambda m: (m.group(1) or '') + '***@', proxy)

def main() -> int:
    parser = argparse.ArgumentParser(description='Local PayRail Hub payment link extract CLI')
    parser.add_argument('--session-file', required=True, help='Path to session JSON or accessToken file')
    parser.add_argument('--rail', default='upi', choices=sorted(SPECS), help='Payment rail to extract (default: upi)')
    parser.add_argument('--proxy', default='', help='Override rail egress proxy')
    args = parser.parse_args()
    spec = get_spec(args.rail)
    raw = open(args.session_file, encoding='utf-8').read()
    proxy = (args.proxy or resolve_rail_proxy(spec.rail_id)).strip()
    token = resolve_upi_access_token(raw, proxy=proxy, region=spec.country)
    if not token:
        print('ERROR: no valid accessToken in session file', file=sys.stderr)
        return 1
    masked = _mask_proxy_url(proxy)
    print(f'rail={spec.rail_id} country={spec.country} currency={spec.currency} proxy={masked}')
    print('extracting…')
    try:
        result = extract_upi_link(raw, proxy=proxy, spec=spec)
    except Exception as exc:
        print(f'FAILED: {exc}', file=sys.stderr)
        return 2
    print(json.dumps({'success': result.get('success'), 'rail_id': spec.rail_id, 'currency': result.get('currency'), 'long_url': result.get('long_url'), 'cs_id': result.get('cs_id'), 'amount': result.get('amount'), 'steps_count': len(result.get('steps') or [])}, ensure_ascii=False, indent=2))
    return 0 if result.get('long_url') else 3
if __name__ == '__main__':
    raise SystemExit(main())
