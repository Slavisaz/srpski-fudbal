#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
srpskifudbal.com — Auto fetch skripta
Povlači vesti iz srpskih ćiriličnih sajtova i upisuje u index.html
GitHub Actions: cron svakih 60 minuta — besplatno
100% legalno: samo naslov + kratki opis + link
"""

import feedparser
import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
import functools


# ═══════════════════════════════════════════════════
# TRANSLITERACIJA latinica → ćirilica (srpska)
# ═══════════════════════════════════════════════════
LAT_CIR = {
    'lj': 'љ', 'nj': 'њ', 'dž': 'џ', 'dj': 'ђ',
    'Lj': 'Љ', 'Nj': 'Њ', 'Dž': 'Џ', 'Dj': 'Ђ',
    'LJ': 'ЉЈ', 'NJ': 'ЊЈ', 'DŽ': 'Џ', 'DJ': 'ЂЈ',
    'a':'а','b':'б','c':'ц','č':'ч','ć':'ћ',
    'd':'д','e':'е','f':'ф','g':'г','h':'х',
    'i':'и','j':'ј','k':'к','l':'л','m':'м',
    'n':'н','o':'о','p':'п','r':'р','s':'с',
    'š':'ш','t':'т','u':'у','v':'в','z':'з','ž':'ж',
    'A':'А','B':'Б','C':'Ц','Č':'Ч','Ć':'Ћ',
    'D':'Д','E':'Е','F':'Ф','G':'Г','H':'Х',
    'I':'И','J':'Ј','K':'К','L':'Л','M':'М',
    'N':'Н','O':'О','P':'П','R':'Р','S':'С',
    'Š':'Ш','T':'Т','U':'У','V':'В','Z':'З','Ž':'Ж',
}

def lat_u_cir(tekst):
    """Prevodi srpsku latinicu u ćirilicu."""
    if not tekst:
        return tekst
    # Digrafi prvo (redosled je važan)
    for lat, cir in [('lj','љ'),('nj','њ'),('dž','џ'),('dj','ђ'),
                     ('Lj','Љ'),('Nj','Њ'),('Dž','Џ'),('Dj','Ђ'),
                     ('LJ','ЉЈ'),('NJ','ЊЈ'),('DŽ','Џ'),('DJ','ЂЈ')]:
        tekst = tekst.replace(lat, cir)
    # Jednoslovna zamena
    rezultat = []
    for ch in tekst:
        rezultat.append(LAT_CIR.get(ch, ch))
    return ''.join(rezultat)


# ═══════════════════════════════════════════════════
# ISPRAVNA PREZIMENA — latinica → ćirilica
# ═══════════════════════════════════════════════════
PREZIMENA = {
    "Vlahovic": "Влаховић", "Vlahović": "Влаховић",
    "Tadic": "Тадић", "Tadić": "Тадић",
    "Milinkovic": "Милинковић", "Milinković": "Милинковић",
    "Milinković-Savić": "Милинковић-Савић",
    "Savic": "Савић", "Savić": "Савић",
    "Mitrovic": "Митровић", "Mitrovič": "Митровић",
    "Jovic": "Јовић", "Jovič": "Јовић",
    "Lukic": "Лукић", "Lukić": "Лукић",
    "Maksimovic": "Максимовић", "Maksimović": "Максимовић",
    "Pavlovic": "Павловић", "Pavlović": "Павловић",
    "Milenkovic": "Миленковић", "Milenković": "Миленковић",
    "Lazovic": "Лазовић", "Lazović": "Лазовић",
    "Zivkovic": "Живковић", "Živković": "Живковић",
    "Grujic": "Грујић", "Grujić": "Грујић",
    "Kostic": "Костић", "Kostić": "Костић",
    "Rajkovic": "Рајковић", "Rajković": "Рајковић",
    "Stojkovic": "Стојковић", "Stojković": "Стојковић",
    "Petrovic": "Петровић", "Petrović": "Петровић",
    "Jovanovic": "Јовановић", "Jovanović": "Јовановић",
    "Nikolic": "Николић", "Nikolić": "Николић",
    "FK Partizan": "ФК Партизан",
    "FK Vojvodina": "ФК Војводина",
    "FK Cukaricki": "ФК Чукарички",
    "FK Čukarički": "ФК Чукарички",
    "FK Spartak": "ФК Спартак",
    "FK Radnik": "ФК Радник",
    "FK Napredak": "ФК Напредак",
    "FK Novi Pazar": "ФК Нови Пазар",
}

def ispravi(tekst):
    if not tekst:
        return tekst
    for lat, cir in PREZIMENA.items():
        tekst = tekst.replace(lat, cir)
    return tekst


# ═══════════════════════════════════════════════════
# RSS FEEDOVI — samo srpski ćirilični sajtovi
# ═══════════════════════════════════════════════════
RSS_FEEDOVI = [
    {
        "naziv": "Танјуг",
        "url":   "SCRAPE:https://www.tanjug.rs/sport/fudbal",
        "backup": None,
        "logo":  "tanjug.rs",
        "uvek":  True,
        "max":   6,
    },
    {
        "naziv": "ФСС",
        "url":   "https://www.fss.rs/sr/rss.html",
        "backup":"https://www.fss.rs/rss",
        "logo":  "fss.rs",
        "uvek":  True,
        "max":   5,
    },
    {
        "naziv": "РТС",
        "url":   "https://www.rts.rs/rss/sekcija/fudbal.xml",
        "backup":"https://www.rts.rs/rss/sport.xml",
        "logo":  "rts.rs",
        "uvek":  False,
        "max":   5,
        "scrape_url": "https://www.rts.rs/sport/fudbal.html",
    },
    {
        "naziv": "Политика",
        "url":   "https://zurnal.politika.rs/scc/rss/fudbal",
        "backup":"https://www.politika.rs/rss/rubrika/sport",
        "logo":  "politika.rs",
        "uvek":  False,
        "max":   5,
        "scrape_url": "https://zurnal.politika.rs/scc/rubrika/19/fudbal",
    },
    {
        "naziv": "Новости",
        "url":   "https://www.novosti.rs/rss/sport.xml",
        "backup":"https://www.novosti.rs/rss/all.xml",
        "logo":  "novosti.rs",
        "uvek":  False,
        "max":   5,
        "scrape_url": "https://www.novosti.rs/sport/fudbal",
    },
]


# ═══════════════════════════════════════════════════
# TANJUG SCRAPER — direktno sa sajta
# ═══════════════════════════════════════════════════
def scrape_tanjug_fudbal():
    """Scrape-uje naslove sa tanjug.rs/sport/fudbal i prevodi u ćirilicu."""
    url = "https://www.tanjug.rs/sport/fudbal"
    vesti = []
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'srpskifudbal.com/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')

        # Pronađi linkove ka vestima — format: /sport/fudbal/BROJ-naslov
        pattern = r'href="(/sport/fudbal/[\w\-]+)"[^>]*>([^<]{15,})</a>'
        matches = re.findall(pattern, html)

        # Alternativni pattern za h2/h3 naslove
        if not matches:
            pattern2 = r'href="(/sport/fudbal/[^"]+)".*?<(?:h[123]|span)[^>]*>([^<]{15,})</(?:h[123]|span)>'
            matches = re.findall(pattern2, html, re.DOTALL)

        seen = set()
        for path, naslov in matches:
            naslov = naslov.strip()
            if not naslov or path in seen or len(naslov) < 15:
                continue
            seen.add(path)

            # Prevedi u ćirilicu
            naslov_cir = lat_u_cir(naslov)
            full_url = f"https://www.tanjug.rs{path}"

            vesti.append({
                "naslov": naslov_cir,
                "opis":   "",
                "url":    full_url,
                "izvor":  "Танјуг",
                "logo":   "tanjug.rs",
                "datum":  datetime.now().strftime("%d. %m. %Y. %H:%M"),
                "slika":  None,
            })

            if len(vesti) >= 10:
                break

        print(f"   ✓ Tanjug scrape: {len(vesti)} vesti")
    except Exception as e:
        print(f"   ✗ Tanjug scrape greška: {e}")

    return vesti

KLJUCNE_RECI = [
    "фудбал", "суперлига", "партизан", "звезда", "войводина",
    "чукарички", "репрезентација", "влаховић", "тадић", "митровић",
    "милинковић", "јовић", "маракана", "хумска", "фсс", "србија",
    "утакмица", "гол", "лига", "куп", "трансфер", "тренер",
    "fudbal", "superliga", "partizan", "zvezda", "vojvodina",
    "cukaricki", "reprezentacija", "vlahovic", "tadic", "mitrovic",
    "marakana", "humska", "fss", "srbija", "utakmica", "transfer",
]

def je_fudbal(tekst, uvek=False):
    if uvek:
        return True
    return any(r in tekst.lower() for r in KLJUCNE_RECI)

def ocisti(tekst):
    if not tekst:
        return ""
    tekst = re.sub(r'<[^>]+>', '', tekst)
    for ent, rep in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"'),('&#\\d+;','')]:
        tekst = re.sub(ent, rep, tekst)
    return re.sub(r'\s+', ' ', tekst).strip()

def datum_iz_entry(entry):
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.strftime("%d. %m. %Y. %H:%M")
    except Exception:
        pass
    return datetime.now().strftime("%d. %m. %Y. %H:%M")


def normalizuj(tekst):
    """Normalizuj naslov za poređenje — samo slova/brojevi, malo slovo."""
    if not tekst:
        return ""
    return re.sub(r'[^\w]', '', tekst.lower())[:50]


def scrape_html_vesti(url, naziv, logo, max_n=5):
    """Generički scraper za HTML stranice bez RSS-a."""
    vesti = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'srpskifudbal.com/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')

        # Pronađi <a href="...">naslov</a> sa bar 15 karaktera u naslovu
        pattern = r'href="(https?://[^"]+)"[^>]*>\s*([^<]{15,})\s*</a>'
        matches = re.findall(pattern, html)
        seen = set()
        for link, naslov in matches:
            naslov = naslov.strip()
            if not naslov or link in seen or len(naslov) < 15:
                continue
            seen.add(link)
            naslov_cir = ispravi(lat_u_cir(naslov))
            vesti.append({
                "naslov": naslov_cir,
                "opis":   "",
                "url":    link,
                "izvor":  naziv,
                "logo":   logo,
                "datum":  datetime.now().strftime("%d. %m. %Y. %H:%M"),
                "slika":  None,
            })
            if len(vesti) >= max_n:
                break
        print(f"   ✓ HTML scrape {naziv}: {len(vesti)} vesti")
    except Exception as e:
        print(f"   ✗ HTML scrape {naziv}: {e}")
    return vesti


# ═══════════════════════════════════════════════════
# POVLAČENJE VESTI
# ═══════════════════════════════════════════════════
def povuci_vesti():
    sve = []
    vidljivi_url = set()
    vidljivi_norm = set()  # dedup po sadržaju naslova

    def dodaj(vest):
        url = vest.get("url", "")
        norm = normalizuj(vest.get("naslov", ""))
        if url in vidljivi_url or norm in vidljivi_norm:
            return False
        vidljivi_url.add(url)
        vidljivi_norm.add(norm)
        sve.append(vest)
        return True

    for fi in RSS_FEEDOVI:
        max_n = fi.get("max", 5)

        # Tanjug — scraper umesto RSS
        if fi["url"].startswith("SCRAPE:"):
            print(f"\n🌐 Scrape-ujem: {fi['naziv']} (tanjug.rs/sport/fudbal)")
            tanjug_vesti = scrape_tanjug_fudbal()
            for v in tanjug_vesti[:max_n]:
                dodaj(v)
            continue

        print(f"\n📡 Povlačim: {fi['naziv']} ({fi['url']})")
        vesti_izvora = 0
        try:
            feed = feedparser.parse(fi["url"], agent="srpskifudbal.com/1.0")
            if (not feed.entries or feed.bozo) and fi.get("backup"):
                print(f"   ⚠ Backup RSS: {fi['backup']}")
                feed = feedparser.parse(fi["backup"])

            if not feed.entries:
                # Pokušaj HTML scrape ako postoji scrape_url
                if fi.get("scrape_url"):
                    print(f"   ⚠ Nema RSS → HTML scrape: {fi['scrape_url']}")
                    html_vesti = scrape_html_vesti(fi["scrape_url"], fi["naziv"], fi["logo"], max_n)
                    for v in html_vesti:
                        if dodaj(v):
                            vesti_izvora += 1
                else:
                    print("   ✗ Nema entija")
                continue

            print(f"   ✓ {len(feed.entries)} entija pronađeno")

            for entry in feed.entries[:30]:
                if vesti_izvora >= max_n:
                    break
                url = getattr(entry, 'link', '')
                if not url:
                    continue

                naslov = ispravi(lat_u_cir(ocisti(getattr(entry, 'title', ''))))
                opis   = ispravi(lat_u_cir(ocisti(getattr(entry, 'summary', ''))))[:300]

                if not je_fudbal(naslov + " " + opis, fi.get("uvek", False)):
                    continue

                slika = None
                if hasattr(entry, 'media_content') and entry.media_content:
                    slika = entry.media_content[0].get('url')
                elif hasattr(entry, 'enclosures') and entry.enclosures:
                    slika = entry.enclosures[0].get('href')

                vest = {
                    "naslov": naslov,
                    "opis":   opis,
                    "url":    url,
                    "izvor":  fi["naziv"],
                    "logo":   fi["logo"],
                    "datum":  datum_iz_entry(entry),
                    "slika":  slika,
                }
                if dodaj(vest):
                    vesti_izvora += 1

            print(f"   ✓ {vesti_izvora} fudbalskih vesti")

        except Exception as e:
            print(f"   ✗ Greška: {e}")

    sve.sort(key=lambda v: v["datum"], reverse=True)
    print(f"\n✅ Ukupno vesti: {len(sve)}")
    return sve[:40]


# ═══════════════════════════════════════════════════
# PROGNOZA DANA
# ═══════════════════════════════════════════════════
UTAKMICE = [
    {"domacin":"ЦЗ Звезда","gost":"ФК Партизан","liga":"Суперлига","datum":"23.03.2026","vreme":"18:00","tip":"1","kvota":2.10,"analiza":"Звезда домаћин, 7 бодова предности.","pouzdanost":4},
    {"domacin":"ФК Чукарички","gost":"ФК Нови Пазар","liga":"Суперлига","datum":"22.03.2026","vreme":"16:00","tip":"1X","kvota":1.55,"analiza":"Чукарички не губи код куће.","pouzdanost":5},
    {"domacin":"ФК Войводина","gost":"ФК Спартак","liga":"Суперлига","datum":"22.03.2026","vreme":"14:30","tip":"ОВ 2.5","kvota":1.80,"analiza":"Обе екипе постижу 2+ голова.","pouzdanost":4},
    {"domacin":"Јувентус","gost":"Наполи","liga":"Серија А","datum":"22.03.2026","vreme":"20:45","tip":"1","kvota":2.30,"analiza":"Влаховић у одличној форми.","pouzdanost":3},
    {"domacin":"Торино","gost":"Лацио","liga":"Серија А","datum":"22.03.2026","vreme":"18:00","tip":"X2","kvota":1.65,"analiza":"МСС одлично у голу.","pouzdanost":4},
]

def prognoza_dana():
    superliga = sorted([u for u in UTAKMICE if "Суперлига" in u["liga"]], key=lambda u: u["pouzdanost"], reverse=True)
    evropa    = sorted([u for u in UTAKMICE if "Суперлига" not in u["liga"]], key=lambda u: u["pouzdanost"], reverse=True)
    izabrane  = superliga[:2] + evropa[:2]
    kvota = round(functools.reduce(lambda a, b: a * b["kvota"], izabrane, 1.0), 2)
    return {
        "datum":          datetime.now().strftime("%d. %m. %Y."),
        "utakmice":       izabrane,
        "ukupna_kvota":   kvota,
        "ulog_primer":    1000,
        "dobitak_primer": round(kvota * 1000, 0),
        "napomena":       "Прогноза је информативног карактера. Игра одговорно. 18+",
    }


# ═══════════════════════════════════════════════════
# UPISIVANJE VESTI U index.html
# ═══════════════════════════════════════════════════
SVG_BOJE = [
    ("#e8f0fb","rgba(0,63,138,.07)"),
    ("#fff0f0","rgba(204,0,0,.06)"),
    ("#f0f7f0","rgba(22,163,74,.06)"),
    ("#fffbf0","rgba(212,160,23,.07)"),
    ("#f0f0fb","rgba(100,0,200,.05)"),
    ("#fff5f0","rgba(204,100,0,.06)"),
]
SLOVA = "АБВГДЂЕЖЗИЈКЛЉМНЊОПРСТЋУФХЦЧЏШ"

def kartica_html(vest, i):
    bg, fg = SVG_BOJE[i % len(SVG_BOJE)]
    sl = SLOVA[i % len(SLOVA)]
    n  = vest['naslov'].replace('"','&quot;').replace('<','&lt;').replace('>','&gt;')
    op = vest.get('opis','')[:140].replace('"','&quot;').replace('<','&lt;').replace('>','&gt;')
    url = vest['url'].replace("'","%27")
    return (
        f'      <div class="nc fi-anim" onclick="window.open(\'{url}\',\'_blank\')" style="cursor:pointer">\n'
        f'        <div class="nc-img"><svg viewBox="0 0 360 150" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="360" height="150" fill="{bg}"/>'
        f'<text x="30" y="125" font-family="serif" font-size="128" font-weight="900" fill="{fg}">{sl}</text>'
        f'<text x="14" y="26" font-family="sans-serif" font-size="9" fill="{fg}" opacity=".5" letter-spacing="2">{vest["izvor"].upper()}</text>'
        f'</svg></div>\n'
        f'        <div class="nc-body">\n'
        f'          <div class="nc-cat">{vest["izvor"]}</div>\n'
        f'          <div class="nc-ttl">{n}</div>\n'
        f'          <div class="nc-blrb">{op}{"..." if len(op)>=140 else ""}</div>\n'
        f'          <div class="nc-meta"><span>{vest["datum"]}</span><span>Прочитај →</span></div>\n'
        f'        </div>\n'
        f'      </div>'
    )

def ubaci_u_html(vesti, azurirano):
    # Probaj index.html u trenutnom i parent direktorijumu
    for path_try in [Path("index.html"), Path("../index.html"), Path("./index.html")]:
        if path_try.exists():
            html_path = path_try
            break
    else:
        print(f"   ✗ index.html nije pronađen!")
        print(f"   Trenutni dir: {Path.cwd()}")
        print(f"   Fajlovi: {[f.name for f in Path.cwd().iterdir() if not f.name.startswith('.')]}")
        return

    sadrzaj = html_path.read_text(encoding="utf-8")

    if "VESTI_START" not in sadrzaj:
        print("   ✗ Markeri VESTI_START nisu u index.html!")
        return

    kartice = "\n".join(kartica_html(v, i) for i, v in enumerate(vesti[:6]))

    novi = re.sub(
        r'<!-- VESTI_START -->.*?<!-- VESTI_END -->',
        f'<!-- VESTI_START -->\n{kartice}\n      <!-- VESTI_END -->',
        sadrzaj, flags=re.DOTALL
    )
    novi = re.sub(
        r'id="poslednje-azuriranje"[^>]*>[^<]*<',
        f'id="poslednje-azuriranje" style="font-family:var(--fu);font-size:11px;color:var(--txt4);margin-left:10px">Ажурирано: {azurirano}<',
        novi
    )

    # 2. SIDEBAR VESTI — 3 naslova u desnom stupcu
    if vesti:
        sidebar_items = ""
        for i, v in enumerate(vesti[:3]):
            border = "border-bottom:1px solid var(--bdr);" if i < 2 else ""
            sidebar_items += (
                f'      <a href="{v["url"]}" target="_blank" class="sv-item" '
                f'style="display:block;padding:12px 14px;{border}text-decoration:none;background:white;transition:background .15s" '
                f'onmouseover="this.style.background=\'var(--off)\'" onmouseout="this.style.background=\'white\'">\n'
                f'        <div style="font-family:var(--fu);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;color:var(--txt3);margin-bottom:3px">{v["izvor"]}</div>\n'
                f'        <div style="font-family:var(--fd);font-size:14px;font-weight:700;color:var(--txt);line-height:1.3">{v["naslov"][:75]}</div>\n'
                f'      </a>\n'
            )
        novi = re.sub(
            r'<!-- SIDEBAR_VESTI_START -->.*?<!-- SIDEBAR_VESTI_END -->',
            f'<!-- SIDEBAR_VESTI_START -->\n{sidebar_items}      <!-- SIDEBAR_VESTI_END -->',
            novi, flags=re.DOTALL
        )

    # 4. TICKER — prvih 8 naslova
    ticker_spans = "\n".join(f'      <span>{v["naslov"][:80]}</span>' for v in vesti[:8])
    novi = re.sub(
        r'<!-- TICKER_START -->.*?<!-- TICKER_END -->',
        f'<!-- TICKER_START -->\n{ticker_spans}\n      <!-- TICKER_END -->',
        novi, flags=re.DOTALL
    )

    html_path.write_text(novi, encoding="utf-8")
    print(f"   ✓ {html_path} ažuriran — vesti: {len(vesti)}, ticker + sidebar")
# ═══════════════════════════════════════════════════
TABELA = [
    {"poz":1,"klub":"ЦЗ Звезда","u":24,"p":17,"n":5,"i":2,"gd":"+34","go":"56-22","bod":56},
    {"poz":2,"klub":"ФК Партизан","u":24,"p":16,"n":6,"i":2,"gd":"+28","go":"48-20","bod":54},
    {"poz":3,"klub":"ФК Войводина","u":24,"p":12,"n":4,"i":8,"gd":"+10","go":"38-28","bod":40},
    {"poz":4,"klub":"ФК Чукарички","u":24,"p":10,"n":6,"i":8,"gd":"+6","go":"34-28","bod":36},
    {"poz":5,"klub":"ФК Спартак","u":24,"p":9,"n":5,"i":10,"gd":"+2","go":"30-28","bod":32},
    {"poz":6,"klub":"ФК Напредак","u":24,"p":8,"n":5,"i":11,"gd":"-4","go":"26-30","bod":29},
    {"poz":7,"klub":"ФК Радник","u":24,"p":7,"n":5,"i":12,"gd":"-8","go":"22-30","bod":26},
    {"poz":8,"klub":"ФК Нови Пазар","u":24,"p":4,"n":4,"i":16,"gd":"-18","go":"18-36","bod":16},
]

STRELCI = [
    {"poz":1,"ime":"А. Максимовић","klub":"ЦЗ Звезда","golovi":14},
    {"poz":2,"ime":"М. Лукић","klub":"ФК Партизан","golovi":11},
    {"poz":3,"ime":"Н. Јовановић","klub":"ФК Чукарички","golovi":9},
    {"poz":4,"ime":"Д. Николић","klub":"ФК Войводина","golovi":8},
    {"poz":5,"ime":"С. Петровић","klub":"ФК Спартак","golovi":7},
]


# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════
def main():
    print("=" * 55)
    print("🇷🇸  SrpskiFudbal.com — Auto fetch skripta")
    print(f"    {datetime.now().strftime('%d.%m.%Y. %H:%M:%S')}")
    print(f"    Radni dir: {Path.cwd()}")
    print("=" * 55)

    # 1. Povuci vesti
    vesti = povuci_vesti()

    # 2. Prognoza dana

    # 3. Snimi JSON
    izlaz = Path("public/data")
    izlaz.mkdir(parents=True, exist_ok=True)

    azurirano_sr = datetime.now().strftime("%d. %m. %Y. у %H:%M")
    podaci = {
        "azurirano":    datetime.now(timezone.utc).isoformat(),
        "azurirano_sr": azurirano_sr,
        "vesti":        vesti,
        "tabela":       TABELA,
        "strelci":      STRELCI,
    }

    json_path = izlaz / "football.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(podaci, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON sačuvan ({os.path.getsize(json_path)/1024:.1f} KB)")

    # 4. Ubaci vesti direktno u index.html
    print("\n📰 Upisujem vesti u index.html...")
    ubaci_u_html(vesti, azurirano_sr)

    print("\n🏁 Završeno!")


if __name__ == "__main__":
    main()
