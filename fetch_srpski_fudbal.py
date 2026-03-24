#!/usr/bin/env python3
"""
Srpski Fudbal — Auto Fetch Script
Runs via GitHub Actions every 30 minutes.
Fetches: Tanjug/Mondo/RTS/Sportski Zurnal news + Superliga table + top scorers
Saves images locally to bypass hotlink protection.
"""

import json, time, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
import feedparser

# ── Config ──────────────────────────────────────────────────────
OUTPUT   = Path('public/data/football.json')
IMG_DIR  = Path('public/data/images')
IMG_DIR.mkdir(parents=True, exist_ok=True)

# Browser-like headers — some sites block bot user agents
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'sr,en;q=0.5',
}

RSS_FEEDS = [
    ('Мондо',           'https://www.mondo.rs/rss/sport/fudbal',        3),
    ('Спортски журнал', 'https://zurnal.politika.rs/rss/sport/fudbal',  2),
    ('РТС',             'https://www.rts.rs/rss/sport/fudbal.rss',      2),
    ('Новости',         'https://www.novosti.rs/rss/sport/fudbal',      2),
    ('ФСС',             'https://fss.rs/rss/vesti',                     1),
]

def ts_sr(dt):
    if not dt:
        return ''
    months = ['', 'јан', 'феб', 'мар', 'апр', 'мај', 'јун',
              'јул', 'авг', 'сеп', 'окт', 'нов', 'дец']
    try:
        return f"{dt.day:02d}. {months[dt.month]}. {dt.year}. {dt.hour:02d}:{dt.minute:02d}"
    except:
        return ''

def fetch_feed(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read()
        feed = feedparser.parse(content)
        print(f'  → {len(feed.entries)} entries')
        return feed
    except Exception as e:
        print(f'  ⚠ Feed error: {e}')
        return None

def get_image_url(entry):
    """Extract image URL from any RSS enclosure or media field."""
    # 1. enclosure — accept regardless of type (Tanjug omits type attr)
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            url = enc.get('href') or enc.get('url', '')
            if url and any(url.lower().endswith(ext) for ext in ('.jpg','.jpeg','.png','.webp','.gif')):
                return url
            # Also accept if type says image
            if url and enc.get('type', '').startswith('image'):
                return url
            # Accept any enclosure URL even without type (Tanjug case)
            if url:
                return url
    # 2. media:thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    # 3. media:content
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            if m.get('url'):
                return m['url']
    return None

def download_image(img_url):
    """Download image locally, return relative path or None."""
    if not img_url or not img_url.startswith('http'):
        return None
    try:
        ext = img_url.split('?')[0].rsplit('.', 1)[-1].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
            ext = 'jpg'
        name = hashlib.md5(img_url.encode()).hexdigest()[:16] + '.' + ext
        local = IMG_DIR / name
        web_path = f'public/data/images/{name}'

        if local.exists() and local.stat().st_size > 500:
            return web_path  # already downloaded

        origin = '/'.join(img_url.split('/')[:3]) + '/'
        req = urllib.request.Request(img_url, headers={
            **HEADERS,
            'Referer': origin,
            'Accept': 'image/webp,image/avif,image/*,*/*;q=0.8',
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            data = r.read()
        if len(data) < 500:
            return None
        local.write_bytes(data)
        print(f'    📷 {name} ({len(data)//1024}KB)')
        return web_path
    except Exception as e:
        print(f'    ⚠ Image failed: {e}')
        return None

def fetch_vesti():
    vesti = []
    for izvor, url, max_items in RSS_FEEDS:
        print(f'\nFetching {izvor} ...')
        feed = fetch_feed(url)
        if not feed or not feed.entries:
            print(f'  ✗ Skipped')
            continue
        count = 0
        for entry in feed.entries[:max_items]:
            title = entry.get('title', '').strip()
            link  = entry.get('link', '').strip()
            if not title or not link:
                continue

            img_url   = get_image_url(entry)
            local_img = download_image(img_url) if img_url else None

            pub = entry.get('published_parsed') or entry.get('updated_parsed')
            dt  = datetime(*pub[:6], tzinfo=timezone.utc) if pub else None

            vesti.append({
                'naslov': title,
                'opis':   '',
                'url':    link,
                'izvor':  izvor,
                'logo':   link.split('/')[2] if '/' in link else '',
                'datum':  ts_sr(dt),
                'slika':  local_img,
            })
            count += 1
        print(f'  ✓ {count} vesti saved')
        time.sleep(0.3)
    return vesti

def main():
    now_utc = datetime.now(timezone.utc)
    print(f'\n=== Srpski Fudbal Fetch — {now_utc.strftime("%d.%m.%Y %H:%M UTC")} ===')

    existing = {}
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding='utf-8'))
        except:
            pass

    vesti = fetch_vesti()
    print(f'\n✓ Total: {len(vesti)} vesti')

    data = {
        'azurirano':    now_utc.isoformat(),
        'azurirano_sr': now_utc.strftime('%d. %m. %Y. у %H:%M'),
        'vesti':        vesti,
        'tabela':       existing.get('tabela', []),
        'strelci':      existing.get('strelci', []),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✓ Saved {OUTPUT} ({OUTPUT.stat().st_size // 1024}KB)')

if __name__ == '__main__':
    main()
