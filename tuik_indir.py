"""
TÜİK Coğrafi İstatistik Portalı (CİP) indirici: il / İBBS-2 göstergeleri.
Çalıştır:  python tuik_indir.py            (katalog + aday göstergelerin özeti + seçili 5 göstergenin verisi)
           python tuik_indir.py --sadece-katalog
Çıktı:     data/raw/tuik_<tarih>/katalog.csv           (TR ve EN adlarıyla gösterge kataloğu)
           data/raw/tuik_<tarih>/aday_ozet.csv         (adaylar: düzey, dönem aralığı, dolu il sayısı)
           data/raw/tuik_<tarih>/<gosterge_kodu>_duzey<d>.csv  (seçili göstergelerin ham verisi, uzun biçim)

Ağ kuralları: bağlantı/okuma zaman aşımı 20 s, 2 yeniden deneme (pytuik içinde üstel bekleme),
istekler arasında 2 s bekleme. Erişim yoksa hatayı kaydedip sıfır olmayan kodla çıkar.
"""
import argparse
import os
import sys
import time
from datetime import date

import pandas as pd
import pytuik
from pytuik.geo.data import MAP_DATA_URL, find_variable, normalize_geo_date

# pytuik 0.1.0'ın geo_data'sında iki sorun var (2026-11-01'de bulundu):
#  1) Değerler Türkçe ondalık virgülle geliyor ("7,5"); pd.to_numeric bunları NaN yapıyor.
#  2) Katalogdaki kayitSayisi (çoğunlukla 5) yalnızca son 5 dönemi döndürüyor.
# Bu yüzden GetMapData'yı pytuik istemcisiyle (zaman aşımı + yeniden deneme) doğrudan çağırıyoruz.
KAYIT_SAYISI = {"yillik": 40, "aylik": 400}

BEKLEME = 2.0

# Aday göstergeler (CİP gösterge kodu -> kısa ad). Kodlar 2026-11-01 tarihli
# CİP kataloğundan (assets/sideMenu.json) alındı.
ADAYLAR = {
    "ISGD-GK18575-O18504": "issizlik_orani",
    "ISGD-GK18575-O18506": "istihdam_orani",
    "INS-GK055-O006": "konut_satis",
    "INS-GK058-O006": "yapi_ruhsati_daire",
    "ISKYT-GK378267475-O12101": "girisim_sayisi",
    "UHS-GK097-O0011": "gsyh_bin_tl",
    "UHS-GK096-O0011": "kisi_basi_gsyh_tl",
    "ADNKS-GK137473-O29001": "nufus",
    "ADNKS-GK140832-O29009": "net_goc_hizi",
    "ses123": "ses_skoru",
    "ULS-GK111403-O12001": "otomobil_aylik",
}

# Modele aday olarak ham verisi kaydedilecek en fazla 5 gösterge: (kod, düzey).
# İşsizlik il düzeyinde yalnızca 2022'den beri var; 2014'ten beri olan İBBS-2 seviyesi alınır.
SECILI = [
    ("ISGD-GK18575-O18504", 2),
    ("INS-GK055-O006", 3),
    ("UHS-GK096-O0011", 3),
    ("ADNKS-GK140832-O29009", 3),
    ("ULS-GK111403-O12001", 3),
]


def veri_cek(istemci, sidemenu, kod, duzey):
    oge = find_variable(sidemenu, kod)
    yuk = istemci.get_json(MAP_DATA_URL, params={
        "kaynak": oge.get("kaynak"), "duzey": duzey, "gostergeNo": kod,
        "kayitSayisi": KAYIT_SAYISI.get(oge.get("period"), 40), "period": oge.get("period"),
    })
    if not yuk.get("veriler"):
        return pd.DataFrame(columns=["code", "date", "ham", "deger"])
    tarihler = [normalize_geo_date(t) for t in yuk.get("tarihler", [])]
    satirlar = []
    for birim in yuk.get("veriler", []):
        for i, t in enumerate(tarihler):
            v = birim.get("veri", [])
            ham = v[i] if i < len(v) else None
            satirlar.append({"code": str(birim.get("duzeyKodu")), "date": t.replace("/", "-"), "ham": ham})
    df = pd.DataFrame(satirlar)
    ham = df["ham"].astype("string")
    # Virgül varsa Türkçe biçim: noktalar binlik ayırıcıdır. Virgül yoksa olduğu gibi çevir.
    virgullu = ham.str.contains(",", regex=False).fillna(False)
    ham = ham.where(~virgullu, ham.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    df["deger"] = pd.to_numeric(ham, errors="coerce")
    return df


def ozetle(df, kod, duzey):
    deger = "deger"
    dolu = df.dropna(subset=[deger])
    donemler = sorted(dolu["date"].unique())
    birim_sayisi = df["code"].nunique()
    # Her dönemde verisi olan birim sayısı; en düşük dönem eksik illeri gösterir
    donem_basi = dolu.groupby("date")["code"].nunique()
    return {
        "kod": kod,
        "duzey": duzey,
        "ilk_donem": donemler[0] if donemler else None,
        "son_donem": donemler[-1] if donemler else None,
        "dolu_donem_sayisi": len(donemler),
        "birim_sayisi": birim_sayisi,
        "donem_basi_min_dolu_birim": int(donem_basi.min()) if len(donem_basi) else 0,
        "bos_oran": round(1 - len(dolu) / max(len(df), 1), 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sadece-katalog", action="store_true")
    args = ap.parse_args()

    klasor = os.path.join("data", "raw", f"tuik_{date.today().isoformat()}")
    os.makedirs(klasor, exist_ok=True)
    istemci = pytuik.TuikClient(timeout=20, retries=2)

    try:
        kat_tr = istemci.geo_variables(lang="tr")
        time.sleep(BEKLEME)
        kat_en = istemci.geo_variables(lang="en")
    except Exception as e:  # ağ / erişim hatası: kanıt olarak kaydet
        with open(os.path.join(klasor, "hata.txt"), "w", encoding="utf-8") as f:
            f.write(f"{pd.Timestamp.now()}  {type(e).__name__}: {e}\n")
        sys.exit(f"TÜİK CİP erişilemedi: {type(e).__name__}: {e}")

    kat = kat_tr.merge(kat_en[["var_num", "var_name"]], on="var_num", suffixes=("_tr", "_en"))
    kat.to_csv(os.path.join(klasor, "katalog.csv"), index=False, encoding="utf-8-sig")
    print(f"Katalog: {len(kat)} gösterge -> {klasor}/katalog.csv")
    if args.sadece_katalog:
        return

    from pytuik.geo.data import _fetch_sidemenu
    sidemenu = _fetch_sidemenu(istemci)
    duzeyler = dict(zip(kat["var_num"], kat["var_levels"]))
    adlar = dict(zip(kat["var_num"], kat["var_name_tr"]))
    ozet = []
    for kod, kisa in ADAYLAR.items():
        for duzey in (3, 2, 4):  # 3 = il, 2 = İBBS-2, 4 = ilçe (yalnızca SES için)
            if duzey not in duzeyler.get(kod, []) or (duzey == 4 and kod != "ses123"):
                continue
            time.sleep(BEKLEME)
            try:
                df = veri_cek(istemci, sidemenu, kod, duzey)
            except Exception as e:
                print(f"!! {kod} düzey {duzey}: {type(e).__name__}: {e}")
                ozet.append({"kod": kod, "duzey": duzey, "hata": str(e)})
                continue
            satir = ozetle(df, kod, duzey)
            satir.update(kisa_ad=kisa, ad=adlar.get(kod))
            ozet.append(satir)
            print(f"OK {kod:26} düzey {duzey}  {satir['ilk_donem']}→{satir['son_donem']}  "
                  f"birim={satir['birim_sayisi']}  min_dolu={satir['donem_basi_min_dolu_birim']}")
            if (kod, duzey) in SECILI:
                df.to_csv(os.path.join(klasor, f"{kod}_duzey{duzey}.csv"),
                          index=False, encoding="utf-8-sig")

    pd.DataFrame(ozet).to_csv(os.path.join(klasor, "aday_ozet.csv"),
                              index=False, encoding="utf-8-sig")
    print(f"Bitti: {klasor}")


if __name__ == "__main__":
    main()
