"""
TCMB EVDS seri kodlarının resmi metaverisini doğrular (Aşama 2.1).
Çalıştır:  export EVDS_API_KEY=...   (anahtar yalnızca ortam değişkeninden okunur)
           python evds_dogrula.py
Çıktı:     data/raw/evds_<tarih>/seri_katalog.csv     (ilgili kategorilerdeki tüm serilerin metaverisi)
           data/raw/evds_<tarih>/kod_dogrulama.csv    (evds.py'deki 7 kod + yeni bazlı TÜFE adayları)
           data/raw/evds_<tarih>/tufe_yeni_aylik.csv  (yeni bazlı TÜFE genel endeksi, bulunursa)

Yöntem: categories -> datagroups (yalnızca kur, faiz, fiyat başlıklı kategoriler) -> serieList.
İstekler arasında 1,5 s beklenir; bağlantı zaman aşımı 20 s, 2 yeniden deneme.
"""
import os
import sys
import time
from datetime import date

import pandas as pd
import requests

ADRES = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
BEKLEME = 1.5
KODLAR = ["TP.FG.J0", "TP.DK.USD.A.YTL", "TP.DK.EUR.A.YTL", "TP.APIFON4",
          "TP.KTF10", "TP.KTF12", "TP.KTFTUK"]
# Taranacak kategoriler (2026-11-01 tarihli categories listesinden):
# 2501 TCMB döviz kurları, 2005 TÜFE (TÜİK), 99940 fiyat endeksleri arşiv, 3002 piyasa verileri,
# 450501/450502 faiz ve kâr payı (akım/stok), 9998002 faiz arşiv, 9995002 piyasa verileri arşiv,
# 5002 konut/inşaat (TÜİK), 1501 işgücü (TÜİK) -> TÜİK il serilerinin EVDS kopyası var mı?
KATEGORILER = [2501, 2005, 99940, 3002, 450501, 450502, 9998002, 9995002, 5002, 1501]


def anahtar():
    k = os.environ.get("EVDS_API_KEY", "").strip()
    if not k:
        sys.exit("EVDS_API_KEY ortam değişkeni yok.")
    return k


def getir(yol, key):
    for deneme in range(3):
        try:
            r = requests.get(ADRES + yol, headers={"key": key}, timeout=(20, 60))
            r.raise_for_status()
            time.sleep(BEKLEME)
            return r.json()
        except requests.RequestException as e:
            # Hata metninde anahtar geçmez (başlıkta gönderiliyor), yine de yalnızca türünü yaz
            print(f"!! {yol.split('&')[0]} deneme {deneme + 1}: {type(e).__name__}")
            time.sleep(BEKLEME * (deneme + 2))
    return None


def main():
    key = anahtar()
    klasor = os.path.join("data", "raw", f"evds_{date.today().isoformat()}")
    os.makedirs(klasor, exist_ok=True)

    kategoriler = pd.DataFrame(getir("categories/type=json", key))
    secili = kategoriler[kategoriler["CATEGORY_ID"].astype(int).isin(KATEGORILER)]
    print(f"{len(kategoriler)} kategori, {len(secili)} tanesi taranacak")

    seriler = []
    for _, kat in secili.iterrows():
        gruplar = getir(f"datagroups/mode=2&code={int(kat['CATEGORY_ID'])}&type=json", key) or []
        for g in gruplar:
            liste = getir(f"serieList/type=json&code={g['DATAGROUP_CODE']}", key) or []
            for s in liste:
                s["CATEGORY_TR"] = kat["TOPIC_TITLE_TR"].strip()
                s["DATAGROUP_NAME"] = g.get("DATAGROUP_NAME")
            seriler.extend(liste)
    katalog = pd.DataFrame(seriler).drop_duplicates("SERIE_CODE")
    sutunlar = ["SERIE_CODE", "SERIE_NAME", "SERIE_NAME_ENG", "FREQUENCY_STR", "DEFAULT_AGG_METHOD",
                "START_DATE", "END_DATE", "DATASOURCE", "DATAGROUP_CODE", "DATAGROUP_NAME", "CATEGORY_TR"]
    katalog = katalog[[c for c in sutunlar if c in katalog.columns]]
    katalog.to_csv(os.path.join(klasor, "seri_katalog.csv"), index=False, encoding="utf-8-sig")
    print(f"Katalog: {len(katalog)} seri")

    # 1) Mevcut kodlar
    dogrulama = katalog[katalog["SERIE_CODE"].isin(KODLAR)].copy()
    dogrulama["kaynak"] = "evds.py"
    eksik = sorted(set(KODLAR) - set(dogrulama["SERIE_CODE"]))
    for k in eksik:
        print(f"!! {k} taranan kategorilerde bulunamadı")
    # 2) Yeni bazlı TÜFE genel endeksi adayları
    ad = katalog["SERIE_NAME"].fillna("")
    tufe = katalog[ad.str.contains("2025=100") & ad.str.contains("TÜFE|Tüketici", regex=True)].copy()
    tufe["kaynak"] = "yeni_tufe_adayi"
    out = pd.concat([dogrulama, tufe])
    out.to_csv(os.path.join(klasor, "kod_dogrulama.csv"), index=False, encoding="utf-8-sig")
    print(out[["SERIE_CODE", "SERIE_NAME", "FREQUENCY_STR", "START_DATE", "END_DATE"]].head(40).to_string())

    # 3) Yeni bazlı TÜFE (2025=100) ve sürdürülen 2003=100 genel endeksi: veriyi indir
    #    Kodlar yukarıdaki katalogdan bulundu (bie_tukfiy2025, bie_tukfiy2003 veri grupları).
    tufe_kodlari = {"TP.TUKFIY2025.GENEL": "tufe_2025_100", "TP.GENENDEKS.T1": "tufe_2003_100_yeni_grup",
                    "TP.FG.J0": "tufe_2003_100_arsiv"}
    sutunlar = {}
    bugun = date.today().strftime("%d-%m-%Y")
    for kod, ad in tufe_kodlari.items():
        js = getir(f"series={kod}&startDate=01-01-2005&endDate={bugun}&type=json", key) or {}
        df = pd.DataFrame(js.get("items", []))
        sutun = kod.replace(".", "_")
        if df.empty or sutun not in df.columns:
            print(f"!! {kod} veri gelmedi")
            continue
        sutunlar[ad] = pd.Series(pd.to_numeric(df[sutun], errors="coerce").values, index=df["Tarih"])
    if sutunlar:
        tufe = pd.DataFrame(sutunlar)
        tufe.index.name = "ay"
        tufe.to_csv(os.path.join(klasor, "tufe_yeni_aylik.csv"), encoding="utf-8-sig")
        print(tufe.dropna(how="all").tail(14).to_string())


if __name__ == "__main__":
    main()
