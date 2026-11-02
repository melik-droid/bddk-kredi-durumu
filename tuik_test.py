"""
TÜİK Coğrafi İstatistik Portalı (il bazında göstergeler) testi.
Gerekli: Python >= 3.10 ve  pip install pytuik
Çalıştır:  python3 tuik_test.py
Çıktı:     data/raw/tuik_katalog.csv  (il bazında tüm göstergelerin listesi)
"""
import os
import pandas as pd
import pytuik

pd.set_option("display.width", 200, "display.max_colwidth", 80)
os.makedirs(os.path.join("data", "raw"), exist_ok=True)

# 1) Gösterge kataloğu
kat = pytuik.geo_variables()
yol = os.path.join("data", "raw", "tuik_katalog.csv")
kat.to_csv(yol, index=False, encoding="utf-8-sig")
print(f"Katalog: {len(kat)} gösterge, kaydedildi -> {yol}")
print("Sütunlar:", list(kat.columns))
print(kat.head(5).to_string(), "\n")

# 2) Projeye yarayabilecek göstergeleri ara
ANAHTAR = ["işsiz", "istihdam", "konut", "girişim", "nüfus", "hasıla",
           "ihracat", "sosyoekonomik", "kredi", "mevduat", "göç", "yapı"]
metin = kat.astype(str).agg(" ".join, axis=1).str.lower()
for k in ANAHTAR:
    eslesen = kat[metin.str.contains(k)]
    print(f"--- '{k}': {len(eslesen)} gösterge")
    if len(eslesen):
        print(eslesen.head(8).to_string(), "\n")

# 3) Örnek: bir göstergenin il bazında verisi
ornek = pytuik.geo_data("1000", level=3)
print("Örnek gösterge 1000, il düzeyi:")
print(ornek.head(10).to_string())
print(f"... {len(ornek)} satır, {ornek['code'].nunique()} il, "
      f"dönemler: {sorted(ornek['date'].unique())[:3]} ... {sorted(ornek['date'].unique())[-3:]}")