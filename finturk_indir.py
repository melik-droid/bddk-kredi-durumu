"""
BDDK FinTürk: 81 il, 7 tablo, 2010-03 → 2026-06 (sektör toplamı) verisini indirir.
Çalıştır:  python3 finturk_indir.py
Çıktı:     data/raw/finturk_<tarih>/tablo_<no>.csv
"""
import os
from datetime import date

import pybrsa

BASLANGIC = (2010, 3)
BITIS = (2026, 6)            # FinTürk'te yayımlanmış son çeyrek
GRUP = 10001                 # 10001 = Sektör toplamı
ILLER = list(range(1, 82))   # 81 il plaka kodu

TABLOLAR = {
    1: "krediler",
    2: "mevduat",
    3: "bireysel_bankacilik",
    4: "secilmis_sektorel_krediler",
    5: "oranlar",
    6: "subeler_ve_nufus",
    7: "altin",
}

klasor = os.path.join("data", "raw", f"finturk_{date.today().isoformat()}")
os.makedirs(klasor, exist_ok=True)

for no, ad in TABLOLAR.items():
    print(f"\n=== Tablo {no}: {ad} ===")
    df = pybrsa.fetch_finturk(
        start_year=BASLANGIC[0], start_month=BASLANGIC[1],
        end_year=BITIS[0], end_month=BITIS[1],
        table_no=no, grup_kod=GRUP, il=ILLER, delay=1.0,
    )
    if df.empty:
        print(f"!! Tablo {no} boş geldi, atlanıyor")
        continue
    yol = os.path.join(klasor, f"tablo_{no}_{ad}.csv")
    df.to_csv(yol, index=False, encoding="utf-8-sig")
    print(f"Kaydedildi: {yol}  ({len(df)} satır, {df['period'].nunique()} dönem)")

print(f"\nBitti. Dosyalar: {klasor}")