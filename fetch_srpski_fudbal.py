#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_srpski_fudbal.py  v2
Povlači RSS vesti sa srpskih fudbalskih portala i upisuje u public/data/football.json
Pokreće se svakih 5 minuta putem GitHub Actions.

Izvori (po prioritetu):
  1. FSS          — fss.rs
  2. Mozzart Sport — mozzartsport.com/rss/1.xml
  3. Tanjug        — tanjug.rs/rss/sport/fudbal
  4. B92 srpski    — b92.net/rss/sport/fudbal/srpski-fudbal
  5. B92 vesti     — b92.net/rss/sport/fudbal/vesti

Pravila:
  - Samo vesti iz poslednjih 24h se prikazuju na vrhu
  - Deduplication po slugovanom naslovu
  - SLIKA SE NE ČUVA (legal issue) — frontend koristi generičke SVG ilustracije
"""

import feedparser
import json
import datetime
import re
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

FEEDS = [
    {"url":"https://www.fss.rs/sr/rss.xml",                       "izvor":"ФСС",               "prioritet":1,"filter_kw":[],"max":5},
    {"url":"https://www.mozzartsport.com/rss/1.xml",               "izvor":"Мозарт Спорт",      "prioritet":2,
     "filter_kw":["фудбал","fudbal","liga","лига","kup","куп","reprezentacija","репрезентација",
                  "premier","champions","transfer","трансфер","superliga","суперлига","srbija","србија"],"max":4},
    {"url":"https://www.tanjug.rs/rss/sport/fudbal",               "izvor":"Танјуг",            "prioritet":3,"filter_kw":[],"max":4},
    {"url":"https://www.b92.net/rss/sport/fudbal/srpski-fudbal",   "izvor":"Б92 Српски фудбал", "prioritet":4,"filter_kw":[],"max":3},
    {"url":"https://www.b92.net/rss/sport/fudbal/vesti",           "izvor":"Б92 Фудбал",        "prioritet":5,"filter_kw":[],"max":3},
]

BELGRADE_TZ = ZoneInfo("Europe/Belgrade")
MAX_24H   = 10
MAX_TOTAL = 20


def slugify(text):
    if not text: return ""
    text = unicodedata.normalize("NFKD", text.lower())
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()[:80]


def format_datum(entry):
    try:
        if hasattr(entry,"published_parsed") and entry.published_parsed:
            import time as _t
            dt = datetime.datetime.fromtimestamp(_t.mktime(entry.published_parsed), tz=BELGRADE_TZ)
        else:
            dt = datetime.datetime.now(tz=BELGRADE_TZ)
        return dt.strftime("%-d. %m. %Y. у %H:%M")
    except:
        return datetime.datetime.now(tz=BELGRADE_TZ).strftime("%-d. %m. %Y. у %H:%M")


def entry_ts(entry):
    try:
        if hasattr(entry,"published_parsed") and entry.published_parsed:
            import time as _t
            return _t.mktime(entry.published_parsed)
    except: pass
    return 0.0


def je_fudbalska(entry, kw):
    if not kw: return True
    t = ((entry.get("title") or "") + " " + (entry.get("summary") or "")).lower()
    return any(k.lower() in t for k in kw)


def povuci_feed(cfg):
    print(f"  → [{cfg['izvor']}] {cfg['url']}")
    try:
        feed = feedparser.parse(cfg["url"], agent="SrpskiFudbalBot/2.0")
        if feed.bozo and not feed.entries:
            print(f"    ⚠ {feed.bozo_exception}"); return []
    except Exception as e:
        print(f"    ✗ {e}"); return []

    vesti = []
    for entry in feed.entries:
        if not je_fudbalska(entry, cfg.get("filter_kw", [])): continue
        naslov = entry.get("title","").strip()
        url    = entry.get("link","").strip()
        if not naslov or not url or len(naslov)<10: continue
        vesti.append({
            "naslov":    naslov,
            "url":       url,
            "izvor":     cfg["izvor"],
            "prioritet": cfg["prioritet"],
            "datum":     format_datum(entry),
            "timestamp": entry_ts(entry),
            "slika":     None,   # legal: ne čuvamo slike iz RSS-a
        })
        if len(vesti) >= cfg.get("max",5): break
    print(f"    ✓ {len(vesti)} vesti")
    return vesti


def main():
    print("🇷🇸 Srpski Fudbal v2 — povlačenje vesti")
    sve = []
    for cfg in FEEDS:
        sve.extend(povuci_feed(cfg))

    # Dedup
    seen, dedup = set(), []
    for v in sve:
        s = slugify(v["naslov"])
        if s and s not in seen:
            seen.add(s); dedup.append(v)

    now_ts = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
    cutoff = now_ts - 86400

    fresh = sorted([v for v in dedup if v["timestamp"]>=cutoff], key=lambda v:(v["prioritet"],-v["timestamp"]))
    old   = sorted([v for v in dedup if v["timestamp"]< cutoff], key=lambda v:(v["prioritet"],-v["timestamp"]))

    final = fresh[:MAX_24H] + old[:(MAX_TOTAL-len(fresh[:MAX_24H]))]

    for v in final:
        v.pop("timestamp",None)
        v.pop("prioritet",None)

    sada    = datetime.datetime.now(tz=datetime.timezone.utc)
    sada_sr = datetime.datetime.now(tz=BELGRADE_TZ).strftime("%-d. %m. %Y. у %H:%M")

    out = Path("public/data/football.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({
        "azurirano":    sada.isoformat(),
        "azurirano_sr": sada_sr,
        "vesti_24h":    len(fresh[:MAX_24H]),
        "vesti":        final,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {len(final)} вести ({len(fresh[:MAX_24H])} из 24ч) → {out}")


if __name__=="__main__":
    main()
