from flask import Flask, request, jsonify
import urllib.request
import urllib.parse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
}

VALID_RANGES = {'1mo', '3mo', '6mo', '1y'}


def fetch_symbol(symbol, range_param='1mo'):
    encoded = urllib.parse.quote(symbol)
    url = f'https://query2.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1d&range={range_param}'
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode('utf-8'))

        chart = raw.get('chart', {})
        error = chart.get('error')
        if error:
            return symbol, {'error': error.get('description', 'Unknown error')}

        results = chart.get('result')
        if not results:
            return symbol, {'error': 'Symbol not found'}

        r = results[0]
        meta = r.get('meta', {})
        timestamps = r.get('timestamp') or []
        quotes = r.get('indicators', {}).get('quote', [{}])
        raw_closes = quotes[0].get('close', []) if quotes else []

        # Build full history array (timestamp + close, skip nulls)
        history = []
        for i, ts in enumerate(timestamps):
            c = raw_closes[i] if i < len(raw_closes) else None
            if c is not None:
                history.append({'t': ts, 'c': round(c, 6)})

        closes = [h['c'] for h in history]

        price = meta.get('regularMarketPrice')
        prev_close = meta.get('previousClose') or (closes[-2] if len(closes) >= 2 else None)

        change = round(price - prev_close, 6) if price and prev_close else 0
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0

        week_ago = closes[-6] if len(closes) >= 6 else (closes[0] if closes else None)
        week_pct = round((price - week_ago) / week_ago * 100, 2) if price and week_ago else None

        month_ago = closes[0] if closes else None
        month_pct = round((price - month_ago) / month_ago * 100, 2) if price and month_ago else None

        return symbol, {
            'price': price,
            'previousClose': prev_close,
            'change': change,
            'changePercent': change_pct,
            'weekChangePercent': week_pct,
            'monthChangePercent': month_pct,
            'currency': meta.get('currency', 'USD'),
            'name': meta.get('shortName') or meta.get('longName') or symbol,
            'dayHigh': meta.get('regularMarketDayHigh'),
            'dayLow': meta.get('regularMarketDayLow'),
            'volume': meta.get('regularMarketVolume'),
            'marketState': meta.get('marketState', 'CLOSED'),
            'fiftyTwoWeekHigh': meta.get('fiftyTwoWeekHigh'),
            'fiftyTwoWeekLow': meta.get('fiftyTwoWeekLow'),
            'sparkline': closes[-20:],
            'history': history,
            'timestamp': meta.get('regularMarketTime'),
        }
    except urllib.error.HTTPError as e:
        return symbol, {'error': f'HTTP {e.code}'}
    except Exception as e:
        return symbol, {'error': str(e)}


@app.route('/', defaults={'path': ''}, methods=['GET', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'OPTIONS'])
def prices(path=None):
    if request.method == 'OPTIONS':
        resp = app.make_default_options_response()
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = '*'
        return resp

    raw = request.args.get('symbols', '')
    range_param = request.args.get('range', '1mo')
    if range_param not in VALID_RANGES:
        range_param = '1mo'

    symbols = [s.strip().upper() for s in raw.split(',') if s.strip()][:30]

    if not symbols:
        resp = jsonify({'error': 'symbols param required'})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 400

    result = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_symbol, s, range_param): s for s in symbols}
        for f in as_completed(futures):
            sym, data = f.result()
            result[sym] = data

    resp = jsonify(result)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp
