#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
srpskifudbal.com — Automatska Python skripta
============================================
Povlači srpske fudbalske vesti iz RSS feedova
+ generiše "Prognoza Dana" tiket

Pokretanje: python fetch_srpski_fudbal.py
GitHub Actions: cron svakih 60 minuta (besplatno)

100% legalno: povlači samo naslov + kratki opis + link
Nikada ne kopira ceo tekst članka.
"""

import feedparser
import json
import os
import re
import random
from datetime import datetime, timezone
from pathlib import Path


# ═══════════════════════════════════════════════════
# ISPRAVNI NAZIVI I PREZIMENA (ćirilica)
# ═══════════════════════════════════════════════════
ISPRAVNA_PREZIMENA = {
    # Latinski → Ćirilica (česta greška u RSS feedovima)
    "Vlahovic":       "Влаховић",
    "Vlahovič":       "Влаховић",
    "Vlahović":       "Влаховић",
    "Tadic":          "Тадић",
    "Tadić":          "Тадић",
    "Milinkovic":     "Милинковић",
    "Milinković":     "Милинковић",
    "Milinković-Savić": "Милинковић-Савић",
    "Savic":          "Савић",
    "Savić":          "Савић",
    "Mitrovic":       "Митровић",
    "Mitrovič":       "Митровић",
    "Mitrovič":       "Митровић",
    "Jovic":          "Јовић",
    "Jovič":          "Јовић",
    "Lukic":          "Лукић",
    "Lukić":          "Лукић",
    "Maksimovic":     "Максимовић",
    "Maksimović":     "Максимовић",
    "Pavlovic":       "Павловић",
    "Pavlović":       "Павловић",
    "Milenkovic":     "Миленковић",
    "Milenković":     "Миленковић",
    "Lazovic":        "Лазовић",
    "Lazović":        "Лазовић",
    "Zivkovic":       "Живковић",
    "Živković":       "Живковић",
    "Grujic":         "Грујић",
    "Grujić":         "Грујић",
    "Kostic":         "Костић",
    "Kostić":         "Костић",
    "Rajkovic":       "Рајковић",
    "Rajković":       "Рајковић",
    "Piksi":          "Пикси",
    "Stojkovic":      "Стојковић",
    "Stojković":      "Стојковић",
    "Petrovic":       "Петровић",
    "Petrović":       "Петровић",
    "Jovanovic":      "Јовановић",
    "Jovanović":      "Јовановић",
    "Nikolic":        "Николић",
    "Nikolić":        "Николић",
    # Klubovi latinski → ćirilica
    "Crvena zvezda":  "Crvena zvezda",  # ostaviti jer se mešaju
    "FK Partizan":    "ФК Партизан",
    "FK Vojvodina":   "ФК Војводина",
    "FK Cukaricki":   "ФК Чукарички",
    "FK Čukarički":   "ФК Чукарички",
    "FK Spartak":     "ФК Спартак",
    "FK Radnik":      "ФК Радник",
    "FK Napredak":    "ФК Напредак",
    "FK Novi Pazar":  "ФК Нови Пазар",
}

def ispravi_tekst(tekst: str) -> str:
    """Ispravlja česta pogrešna pisanja prezimena i naziva."""
    if not tekst:
        return tekst
    for pogresno, tacno in ISPRAVNA_PREZIMENA.items():
        tekst = tekst.replace(pogresno, tacno)
    return tekst


# ═══════════════════════════════════════════════════
# RSS FEEDOVI — srpski sportski portali
# Legalno: koristimo samo naslov, kratki opis i URL
# ═══════════════════════════════════════════════════
RSS_FEEDOVI = [
    {
        "naziv":  "Telegraf Sport",
        "url":    "https://www.telegraf.rs/sport/fudbal/rss",
        "backup": "https://www.telegraf.rs/rss",
        "logo":   "telegraf.rs",
    },
    {
        "naziv":  "Nova.rs Sport",
        "url":    "https://nova.rs/sport/fudbal/feed/",
        "backup": "https://nova.rs/feed/",
        "logo":   "nova.rs",
    },
    {
        "naziv":  "Novosti Sport",
        "url":    "https://www.novosti.rs/rss/sport.xml",
        "backup": "https://www.novosti.rs/rss/all.xml",
        "logo":   "novosti.rs",
    },
    {
        "naziv":  "Sportska centrala",
        "url":    "https://www.sportskacentrala.com/feed/",
        "backup": None,
        "logo":   "sportskacentrala.com",
    },
    {
        "naziv":  "Meridian Sport",
        "url":    "https://meridiansport.rs/fudbal/superliga-srbije-domaci-fudbal/feed/",
        "backup": "https://meridiansport.rs/feed/",
        "logo":   "meridiansport.rs",
    },
]

# Ključne reči za filtriranje srpskog fudbala
KLJUCNE_RECI = [
    "zvezda", "partizan", "vojvodina", "čukarički", "cukarički",
    "superliga", "srbija", "srbija", "репрезентација", "reprezentacija",
    "влаховић", "vlahović", "тадић", "tadić", "митровић", "mitrović",
    "милинковић", "milinković", "јовић", "jović", "хумска", "humska",
    "маракана", "marakana", "suперлига", "superliga srbije",
    "fss", "фсс", "superliga",
]

def sadrzi_srpski_fudbal(tekst: str) -> bool:
    """Proverava da li vest govori o srpskom fudbalu."""
    tekst_lower = tekst.lower()
    return any(rec in tekst_lower for rec in KLJUCNE_RECI)

def ocisti_html(tekst: str) -> str:
    """Uklanja HTML tagove iz teksta."""
    if not tekst:
        return ""
    tekst = re.sub(r'<[^>]+>', '', tekst)
    tekst = re.sub(r'&amp;', '&', tekst)
    tekst = re.sub(r'&lt;', '<', tekst)
    tekst = re.sub(r'&gt;', '>', tekst)
    tekst = re.sub(r'&quot;', '"', tekst)
    tekst = re.sub(r'&#\d+;', '', tekst)
    tekst = re.sub(r'\s+', ' ', tekst).strip()
    return tekst

def parsiraj_datum(entry) -> str:
    """Parsira datum iz RSS entrija."""
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.strftime("%d. %m. %Y. %H:%M")
    except Exception:
        pass
    return datetime.now().strftime("%d. %m. %Y. %H:%M")

def povuci_vesti() -> list:
    """Povlači vesti iz svih RSS feedova i filtrira srpski fudbal."""
    sve_vesti = []
    vidljivi_url = set()

    for feed_info in RSS_FEEDOVI:
        print(f"\n📡 Povlačim: {feed_info['naziv']} ({feed_info['url']})")
        try:
            feed = feedparser.parse(
                feed_info["url"],
                agent="srpskifudbal.com RSS Agregator/1.0"
            )

            # Ako feed nije uspeo, pokušaj backup
            if feed.bozo and feed_info.get("backup"):
                print(f"   ⚠ Pokušavam backup: {feed_info['backup']}")
                feed = feedparser.parse(feed_info["backup"])

            if not feed.entries:
                print(f"   ✗ Nema entija u feedu")
                continue

            print(f"   ✓ Pronađeno {len(feed.entries)} entija")
            broj_srpskih = 0

            for entry in feed.entries[:30]:  # max 30 po feedu
                url = getattr(entry, 'link', '')
                if not url or url in vidljivi_url:
                    continue

                naslov = ocisti_html(getattr(entry, 'title', ''))
                opis   = ocisti_html(getattr(entry, 'summary', ''))[:300]

                # Filtriraj samo srpski fudbal
                if not sadrzi_srpski_fudbal(naslov + " " + opis):
                    continue

                # Ispravi prezimena
                naslov = ispravi_tekst(naslov)
                opis   = ispravi_tekst(opis)

                # Uzmi sliku ako postoji
                slika = None
                if hasattr(entry, 'media_content') and entry.media_content:
                    slika = entry.media_content[0].get('url')
                elif hasattr(entry, 'enclosures') and entry.enclosures:
                    slika = entry.enclosures[0].get('href')

                vest = {
                    "naslov":  naslov,
                    "opis":    opis,
                    "url":     url,
                    "izvor":   feed_info["naziv"],
                    "logo":    feed_info["logo"],
                    "datum":   parsiraj_datum(entry),
                    "slika":   slika,
                }

                sve_vesti.append(vest)
                vidljivi_url.add(url)
                broj_srpskih += 1

            print(f"   ✓ {broj_srpskih} srpskih fudbalskih vesti")

        except Exception as e:
            print(f"   ✗ Greška: {e}")
            continue

    # Sortiraj po datumu (najnovije prvo)
    sve_vesti.sort(key=lambda v: v["datum"], reverse=True)
    print(f"\n✅ Ukupno srpskih fudbalskih vesti: {len(sve_vesti)}")
    return sve_vesti[:50]  # max 50 vesti


# ═══════════════════════════════════════════════════
# PROGNOZA DANA — Tiket
# Bira 3-5 utakmica i generiše prognozу
# ═══════════════════════════════════════════════════

# Baza utakmica za prognoze (ažuriraj svake nedelje)
# U produkciji: povuci iz football-data.org /matches endpoint
UTAKMICE_BAZA = [
    # Superliga Srbije
    {
        "domacin":  "ЦЗ Звезда",
        "gost":     "ФК Партизан",
        "liga":     "Суперлига Србије",
        "datum":    "23.03.2026",
        "vreme":    "18:00",
        "tip":      "1",          # домаћин победа
        "kvota":    2.10,
        "analiza":  "Звезда домаћин, 7 бодова предности — јак фаворит.",
        "pouzdanost": 4,          # 1-5
    },
    {
        "domacin":  "ФК Чукарички",
        "gost":     "ФК Нови Пазар",
        "liga":     "Суперлига Србије",
        "datum":    "22.03.2026",
        "vreme":    "16:00",
        "tip":      "1X",
        "kvota":    1.55,
        "analiza":  "Чукарички не губи код куће у овом полусезону.",
        "pouzdanost": 5,
    },
    {
        "domacin":  "ФК Войводина",
        "gost":     "ФК Спартак",
        "liga":     "Суперлига Србије",
        "datum":    "22.03.2026",
        "vreme":    "14:30",
        "tip":      "ОВ 2.5",
        "kvota":    1.80,
        "analiza":  "Обе екипе постижу просечно 2+ гола по мечу.",
        "pouzdanost": 4,
    },
    # Светске лиге — српски играчи у акцији
    {
        "domacin":  "Јувентус",
        "gost":     "Наполи",
        "liga":     "Серија А",
        "datum":    "22.03.2026",
        "vreme":    "20:45",
        "tip":      "1",
        "kvota":    2.30,
        "analiza":  "Влаховић у одличној форми (18 голова), Јувентус борац за Скудето.",
        "pouzdanost": 3,
    },
    {
        "domacin":  "Торино",
        "gost":     "Лацио",
        "liga":     "Серија А",
        "datum":    "22.03.2026",
        "vreme":    "18:00",
        "tip":      "X2",
        "kvota":    1.65,
        "analiza":  "МСС одлично у голу — Торино тежак домаћин али Лацио путује добро.",
        "pouzdanost": 4,
    },
    {
        "domacin":  "Аjакс",
        "gost":     "Фенербахче",
        "liga":     "Пријатељска",
        "datum":    "21.03.2026",
        "vreme":    "19:00",
        "tip":      "1",
        "kvota":    1.90,
        "analiza":  "Тадић против бившег клуба — Ајакс јаки код куће.",
        "pouzdanost": 3,
    },
]

def izracunaj_ukupnu_kvotu(utakmice: list) -> float:
    """Množenje svih kvota za kombinovani tiket."""
    ukupno = 1.0
    for u in utakmice:
        ukupno *= u["kvota"]
    return round(ukupno, 2)

def generisi_prognoza_dana() -> dict:
    """
    Bira 3-5 utakmica i pravi tiket dana.
    Prioritet: pouzdanost 4-5, kombinacija srpskih + evropskih.
    """
    # Sortiraj po pouzdanosti
    sortirane = sorted(UTAKMICE_BAZA, key=lambda u: u["pouzdanost"], reverse=True)

    # Uzmi top 2 Superliga + 1-2 Serija A/Evropa
    superliga = [u for u in sortirane if "Суперлига" in u["liga"]]
    evropa    = [u for u in sortirane if "Суперлига" not in u["liga"]]

    # Biraj 2 superliga + 2 evropa = 4 utakmica
    izabrane = superliga[:2] + evropa[:2]

    # Ako nemamo dovoljno, dopuni random iz baze
    if len(izabrane) < 3:
        preostale = [u for u in sortirane if u not in izabrane]
        izabrane += preostale[:3 - len(izabrane)]

    ukupna_kvota = izracunaj_ukupnu_kvotu(izabrane)

    return {
        "datum":        datetime.now().strftime("%d. %m. %Y."),
        "vreme":        datetime.now().strftime("%H:%M"),
        "utakmice":     izabrane,
        "ukupna_kvota": ukupna_kvota,
        "ulog_primer":  1000,
        "dobitak_primer": round(ukupna_kvota * 1000, 0),
        "napomena":      (
            "Прогноза је искључиво информативног карактера. "
            "Клађење је забавни садржај — играј одговорно. "
            "Само за особе старије од 18 година."
        ),
    }


# ═══════════════════════════════════════════════════
# STATISTIKE SUPERLIGE (placeholder — zameni API)
# ═══════════════════════════════════════════════════
TABELA_SUPERLIGA = [
    {"poz":1, "klub":"ЦЗ Звезда",     "u":24,"p":17,"n":5,"i":2, "gd":"+34","go":"56-22","bod":56,"forma":"ПППНП"},
    {"poz":2, "klub":"ФК Партизан",   "u":24,"p":16,"n":6,"i":2, "gd":"+28","go":"48-20","bod":54,"forma":"ППППИ"},
    {"poz":3, "klub":"ФК Войводина",  "u":24,"p":12,"n":4,"i":8, "gd":"+10","go":"38-28","bod":40,"forma":"ПИНПН"},
    {"poz":4, "klub":"ФК Чукарички", "u":24,"p":10,"n":6,"i":8, "gd":"+6", "go":"34-28","bod":36,"forma":"ННПИП"},
    {"poz":5, "klub":"ФК Спартак",    "u":24,"p":9, "n":5,"i":10,"gd":"+2", "go":"30-28","bod":32,"forma":"ИППНИ"},
    {"poz":6, "klub":"ФК Напредак",   "u":24,"p":8, "n":5,"i":11,"gd":"-4", "go":"26-30","bod":29,"forma":"НИИ ПН"},
    {"poz":7, "klub":"ФК Радник",     "u":24,"p":7, "n":5,"i":12,"gd":"-8", "go":"22-30","bod":26,"forma":"ПИНИИ"},
    {"poz":8, "klub":"ФК Нови Пазар", "u":24,"p":4, "n":4,"i":16,"gd":"-18","go":"18-36","bod":16,"forma":"ИИНИИ"},
]

STRELCI = [
    {"poz":1, "ime":"А. Максимовић", "klub":"ЦЗ Звезда",     "golovi":14},
    {"poz":2, "ime":"М. Лукић",      "klub":"ФК Партизан",   "golovi":11},
    {"poz":3, "ime":"Н. Јовановић",  "klub":"ФК Чукарички", "golovi":9},
    {"poz":4, "ime":"Д. Николић",    "klub":"ФК Войводина",  "golovi":8},
    {"poz":5, "ime":"С. Петровић",   "klub":"ФК Спартак",    "golovi":7},
]


# ═══════════════════════════════════════════════════
# GLAVNI PROGRAM
# ═══════════════════════════════════════════════════
def main():
    print("=" * 55)
    print("🇷🇸  SrpskiFudbal.com — Auto fetch skripta")
    print(f"    {datetime.now().strftime('%d.%m.%Y. %H:%M:%S')}")
    print("=" * 55)

    # 1. Povuci vesti
    vesti = povuci_vesti()

    # 2. Generiši prognoza dana
    print("\n🎯 Generišem prognoza dana tiket...")
    prognoza = generisi_prognoza_dana()
    print(f"   ✓ {len(prognoza['utakmice'])} utakmica, ukupna kvota: {prognoza['ukupna_kvota']}")

    # 3. Složi sve u jedan JSON
    podaci = {
        "azurirano":     datetime.now(timezone.utc).isoformat(),
        "azurirano_sr":  datetime.now().strftime("%d. %m. %Y. u %H:%M"),
        "vesti":         vesti,
        "prognoza_dana": prognoza,
        "tabela":        TABELA_SUPERLIGA,
        "strelci":       STRELCI,
        "statistike": {
            "ukupno_vesti": len(vesti),
            "izvori":       list({v["izvor"] for v in vesti}),
        }
    }

    # 4. Snimi
    izlaz = Path("public/data")
    izlaz.mkdir(parents=True, exist_ok=True)
    izlazni_fajl = izlaz / "football.json"

    with open(izlazni_fajl, "w", encoding="utf-8") as f:
        json.dump(podaci, f, ensure_ascii=False, indent=2)

    velicina = os.path.getsize(izlazni_fajl) / 1024
    print(f"\n✅ Sačuvano → {izlazni_fajl} ({velicina:.1f} KB)")
    print(f"   Vesti: {len(vesti)}")
    print(f"   Prognoza kvota: {prognoza['ukupna_kvota']}x")
    print(f"   Primer dobitka (1000 RSD): {prognoza['dobitak_primer']} RSD")
    print("\n🏁 Završeno!")


if __name__ == "__main__":
    main()
