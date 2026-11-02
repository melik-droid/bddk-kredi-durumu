"""
TCMB EVDS: 2010-01'den bugüne aylık makro serileri indirir.
Çalıştır:  python3 evds.py
           (anahtarı her seferinde sormasın istersen:  export EVDS_API_KEY=...)
Çıktı:     data/raw/evds_<tarih>/makro_aylik.csv
           data/raw/evds_<tarih>/makro_ceyreklik.csv   (FinTürk'le birleştirmeye hazır)
"""
import os
import getpass
from datetime import date

import pandas as pd
import requests

API_KEY = os.environ.get("EVDS_API_KEY") or getpass.getpass("EVDS API anahtarı: ").strip()
ADRES = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
BAS = "01-01-2010"
BIT = date.today().strftime("%d-%m-%Y")

# kod: (sütun adı, aylığa çevirme yöntemi, çeyreğe çevirme yöntemi, doğrulandı mı)
SERILER = {
    "TP.FG.J0":        ("tufe",            "last", "last", True),
    "TP.DK.USD.A.YTL": ("usd_try",         "avg",  "mean", True),
    "TP.DK.EUR.A.YTL": ("eur_try",         "avg",  "mean", False),
    "TP.APIFON4":      ("fonlama_faizi",   "avg",  "mean", False),
    "TP.KTF10":        ("ihtiyac_faizi",   "avg",  "mean", False),
    "TP.KTF12":        ("konut_faizi",     "avg",  "mean", False),
    "TP.KTFTUK":       ("tuketici_faizi",  "avg",  "mean", False),
}


def cek(kod, agg):
    url = (f"{ADRES}series={kod}&startDate={BAS}&endDate={BIT}"
           f"&type=json&frequency=5&aggregationTypes={agg}")
    r = requests.get(url, headers={"key": API_KEY}, timeout=60)
    r.raise_for_status()
    items = r.json().get("items", [])
    sutun = kod.replace(".", "_")
    df = pd.DataFrame(items)
    if df.empty or sutun not in df.columns:
        return None
    df["tarih"] = pd.to_datetime(df["Tarih"], format="%Y-%m").dt.to_period("M")
    return df.set_index("tarih")[sutun].astype(float)


klasor = os.path.join("data", "raw", f"evds_{date.today().isoformat()}")
os.makedirs(klasor, exist_ok=True)

aylik = {}
basarisiz = []
for kod, (ad, agg, _, dogru) in SERILER.items():
    try:
        s = cek(kod, agg)
    except Exception as e:
        s = None
        print(f"!! {kod:18} hata: {e}")
    if s is None or s.dropna().empty:
        basarisiz.append(kod)
        print(f"!! {kod:18} veri gelmedi ({ad})")
        continue
    s = s.dropna()
    aylik[ad] = s
    not_ = "" if dogru else "  <- kodu EVDS'de bir kez kontrol et"
    print(f"OK {kod:18} {ad:16} {s.index.min()} → {s.index.max()}  ({len(s)} ay){not_}")

if not aylik:
    raise SystemExit("Hiç seri gelmedi, anahtarı kontrol et.")

aylik_df = pd.DataFrame(aylik)
aylik_df.index.name = "ay"
aylik_df.to_csv(os.path.join(klasor, "makro_aylik.csv"), encoding="utf-8-sig")

# Çeyreklik: TÜFE çeyrek sonu değeri, kur ve faizler çeyrek ortalaması
kural = {SERILER[k][0]: SERILER[k][2] for k in SERILER if SERILER[k][0] in aylik_df}
ceyrek_df = aylik_df.groupby(aylik_df.index.asfreq("Q")).agg(kural)
ceyrek_df.index.name = "ceyrek"
# FinTürk CSV'lerindeki "period" sütunuyla eşleşsin: 2024-03, 2024-06 ...
ceyrek_df.insert(0, "period", [f"{p.year}-{p.quarter * 3:02d}" for p in ceyrek_df.index])
ceyrek_df.to_csv(os.path.join(klasor, "makro_ceyreklik.csv"), encoding="utf-8-sig")

print(f"\nKaydedildi: {klasor}  ({len(aylik_df)} ay, {len(ceyrek_df)} çeyrek)")
if basarisiz:
    print("Gelmeyen seriler:", ", ".join(basarisiz))
if "tufe" in aylik and aylik["tufe"].index.max() < pd.Period(date.today(), "M") - 3:
    print("DİKKAT: TÜFE serisi erken bitiyor; baz yılı değişmiş olabilir.")