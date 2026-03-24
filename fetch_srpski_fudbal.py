#!/usr/bin/env python3
"""
Srpski Fudbal — Auto Fetch Script
Runs via GitHub Actions every 30 minutes.
Fetches: Tanjug/Mondo/RTS/Sportski Zurnal news + Superliga table + top scorers
Saves Mondo images locally to bypass hotlink protection.
"""

import json, os, re, time, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
import feedparser

# ── Config ──────────────────────────────────────────────────────
OUTPUT   = Path('public/data/football.json')
IMG_DIR  = Path('public/data/images')
IMG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; SrpskiFudbalBot/1.0)'}

RSS_FEEDS = [
    ('Танјуг',           'https://www.tanjug.rs/rss/sport/fudbal',      3),
    ('Мондо',            'https://www.mondo.rs/rss/sport/fudbal',        3),
    ('Спортски журнал',  'https://zurnal.politika.rs/rss/sport/fudbal',  2),
    ('РТС',              'https://www.rts.rs/rss/sport/fudbal.rss',      2),
    ('Новости',          'https://www.novosti.rs/rss/sport/fudbal',      2),
    ('ФСС',              'https://fss.rs/rss/vesti',                     1),
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

def fetch_feed(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read()
        return feedparser.parse(content)
    except Exception as e:
        print(f'  ⚠ Feed error {url}: {e}')
        return None

def download_image(img_url, izvor):
    """Download image locally, return relative web path or None."""
    if not img_url:
        return None
    try:
        # Stable filename from URL hash
        ext = img_url.split('?')[0].split('.')[-1].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
            ext = 'jpg'
        name = hashlib.md5(img_url.encode()).hexdigest()[:16] + '.' + ext
        local = IMG_DIR / name
        web_path = f'public/data/images/{name}'

        # Skip if already downloaded
        if local.exists() and local.stat().st_size > 1000:
            return web_path

        req = urllib.request.Request(img_url, headers={
            **HEADERS,
            'Referer': '/'.join(img_url.split('/')[:3]) + '/',
            'Accept': 'image/webp,image/*,*/*',
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
        if len(data) < 500:
            return None
        local.write_bytes(data)
        print(f'  📷 Saved image: {name} ({len(data)//1024}KB)')
        return web_path
    except Exception as e:
        print(f'  ⚠ Image download failed {img_url}: {e}')
        return None

def fetch_vesti():
    vesti = []
    for izvor, url, max_items in RSS_FEEDS:
        print(f'Fetching {izvor}...')
        feed = fetch_feed(url)
        if not feed or not feed.entries:
            print(f'  ✗ No entries')
            continue
        count = 0
        for entry in feed.entries[:max_items]:
            title = entry.get('title', '').strip()
            link  = entry.get('link', '').strip()
            if not title or not link:
                continue

            # Get image from enclosure or media
            img_url = None
            if hasattr(entry, 'enclosures') and entry.enclosures:
                enc = entry.enclosures[0]
                if enc.get('type', '').startswith('image'):
                    img_url = enc.get('href') or enc.get('url')
            if not img_url and hasattr(entry, 'media_thumbnail'):
                img_url = entry.media_thumbnail[0].get('url')
            if not img_url and hasattr(entry, 'media_content'):
                for m in entry.media_content:
                    if m.get('medium') == 'image' or m.get('type','').startswith('image'):
                        img_url = m.get('url')
                        break

            # Download image locally (important for Mondo hotlink protection)
            local_img = download_image(img_url, izvor) if img_url else None

            # Parse date
            pub = entry.get('published_parsed') or entry.get('updated_parsed')
            dt = datetime(*pub[:6], tzinfo=timezone.utc) if pub else None

            vesti.append({
                'naslov': title,
                'opis':   '',
                'url':    link,
                'izvor':  izvor,
                'logo':   link.split('/')[2] if '/' in link else '',
                'datum':  ts_sr(dt),
                'slika':  local_img,   # local path, served by GitHub Pages
            })
            count += 1
        print(f'  ✓ {count} vesti')
        time.sleep(0.5)
    return vesti

# ── Main ────────────────────────────────────────────────────────
def main():
    now_utc = datetime.now(timezone.utc)
    print(f'\n=== Srpski Fudbal Fetch — {now_utc.strftime("%d.%m.%Y %H:%M UTC")} ===\n')

    # Load existing data to preserve tabela/strelci if feed fails
    existing = {}
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding='utf-8'))
        except:
            pass

    vesti = fetch_vesti()
    print(f'\n✓ Total vesti: {len(vesti)}')

    data = {
        'azurirano':    now_utc.isoformat(),
        'azurirano_sr': now_utc.strftime('%d. %m. %Y. у %H:%M'),
        'vesti':        vesti,
        'tabela':       existing.get('tabela', []),
        'strelci':      existing.get('strelci', []),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✓ Saved {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)')

if __name__ == '__main__':
    main()
