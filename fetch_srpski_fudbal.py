#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_srpski_fudbal.py
Povlači RSS vesti sa srpskih fudbalskih portala i upisuje u public/data/football.json
Pokreće se svakih 30 minuta putem GitHub Actions.
"""

import feedparser
import json
import datetime
import re
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Konfiguracija feedova ──────────────────────────────────────────────────────
FEEDS = [
    {
        "url": "https://mondo.rs/rss/sport",
        "izvor": "Мондо",
        "logo": "mondo.rs",
        "filter_kw": ["фудбал", "fudbal", "liga", "лига", "kup", "куп",
                      "reprezentacija", "репрезентација", "premier", "champions",
                      "transfer", "трансфер", "SuperSport", "superliga"],
    },
    {
        "url": "https://www.tanjug.rs/rss/sport/fudbal",
        "izvor": "Танјуг",
        "logo": "tanjug.rs",
        "filter_kw": [],  # sve su fudbalske
    },
    {
        "url": "https://www.kurir.rs/rss/sport/fudbal",
        "izvor": "Курир",
        "logo": "kurir.rs",
        "filter_kw": [],  # sve su fudbalske
    },
]

BELGRADE_TZ = ZoneInfo("Europe/Belgrade")
MAX_PO_FEEDU = 5   # maksimalno vesti po izvoru
MAX_UKUPNO  = 30  # ukupni limit


def format_datum(entry) -> str:
    """Formatira datum u srpski format: '24. 03. 2026. у 15:18'"""
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            import time as _time
            ts = _time.mktime(entry.published_parsed)
            dt = datetime.datetime.fromtimestamp(ts, tz=BELGRADE_TZ)
        else:
            dt = datetime.datetime.now(tz=BELGRADE_TZ)
        return dt.strftime("%-d. %m. %Y. у %H:%M")
    except Exception:
        return datetime.datetime.now(tz=BELGRADE_TZ).strftime("%-d. %m. %Y. у %H:%M")


def izvuci_sliku(entry) -> str | None:
    """Pokušava da pronađe sliku iz različitih RSS polja."""
    # 1. enclosures
    if getattr(entry, "enclosures", None):
        for enc in entry.enclosures:
            url = getattr(enc, "url", None) or getattr(enc, "href", None)
            if url and re.search(r"\.(jpe?g|png|webp)", url, re.I):
                return url

    # 2. media_content
    if getattr(entry, "media_content", None):
        for mc in entry.media_content:
            url = mc.get("url", "")
            if url:
                return url

    # 3. media_thumbnail
    if getattr(entry, "media_thumbnail", None):
        url = entry.media_thumbnail[0].get("url", "")
        if url:
            return url

    # 4. Pretraži summary/content za <img src="...">
    for field in ("summary", "content"):
        text = ""
        val = getattr(entry, field, None)
        if isinstance(val, list) and val:
            text = val[0].get("value", "")
        elif isinstance(val, str):
            text = val
        if text:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', text, re.I)
            if m:
                return m.group(1)

    return None


def je_fudbalska(entry, filter_kw: list) -> bool:
    """Ako nema filter_kw, prolazi sve. Inače traži ključne reči u naslovu/opisu."""
    if not filter_kw:
        return True
    tekst = (
        (entry.get("title") or "") + " " +
        (entry.get("summary") or "")
    ).lower()
    return any(kw.lower() in tekst for kw in filter_kw)


def povuci_feed(cfg: dict) -> list:
    """Povlači i parsira jedan RSS feed, vraća listu vest-objekata."""
    print(f"  → Povlačim: {cfg['url']}")
    try:
        feed = feedparser.parse(cfg["url"], agent="SrpskiFudbalBot/1.0")
        if feed.bozo and not feed.entries:
            print(f"    ⚠ Greška pri parsiranju: {feed.bozo_exception}")
            return []
    except Exception as e:
        print(f"    ✗ Izuzetak: {e}")
        return []

    vesti = []
    for entry in feed.entries:
        if not je_fudbalska(entry, cfg.get("filter_kw", [])):
            continue

        naslov = entry.get("title", "").strip()
        url    = entry.get("link", "").strip()
        if not naslov or not url:
            continue

        opis  = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()
        slika = izvuci_sliku(entry)
        datum = format_datum(entry)

        vesti.append({
            "naslov": naslov,
            "opis":   opis[:300] if opis else "",
            "url":    url,
            "izvor":  cfg["izvor"],
            "logo":   cfg["logo"],
            "datum":  datum,
            "slika":  slika,
        })

        if len(vesti) >= MAX_PO_FEEDU:
            break

    print(f"    ✓ {len(vesti)} vesti")
    return vesti


def main():
    print("🇷🇸 Srpski Fudbal — povlačenje vesti")
    sve_vesti = []

    for cfg in FEEDS:
        vesti = povuci_feed(cfg)
        sve_vesti.extend(vesti)

    # Ograniči ukupan broj
    sve_vesti = sve_vesti[:MAX_UKUPNO]

    sada = datetime.datetime.now(tz=datetime.timezone.utc)
    sada_sr = datetime.datetime.now(tz=BELGRADE_TZ).strftime("%-d. %m. %Y. у %H:%M")

    izlaz = {
        "azurirano":    sada.isoformat(),
        "azurirano_sr": sada_sr,
        "vesti":        sve_vesti,
    }

    out_path = Path("public/data/football.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(izlaz, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"✅ Upisano {len(sve_vesti)} vesti → {out_path}")


if __name__ == "__main__":
    main()
