"""Ham veriyi okuyup il x çeyrek analiz panelini kurar.

Kaynaklar (salt okunur):
  data/raw/finturk_2026-10-30/   BDDK FinTürk, 7 tablo, 81 il, 2010-03 → 2026-06
  data/raw/evds_2026-10-30/      TCMB EVDS makro (aylık + çeyreklik)
  data/raw/tuik_2026-11-01/      TÜİK CİP il göstergeleri, TÜFE tabloları, il sınırları
Çıktılar:
  data/interim/tufe_zincir.csv, data/interim/il_komsuluk.csv, data/interim/panel.parquet
"""
import json
import os
import re
import warnings

import numpy as np
import pandas as pd

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(KOK, "data", "raw")
INTERIM = os.path.join(KOK, "data", "interim")
FINTURK = os.path.join(RAW, "finturk_2026-10-30")
EVDS = os.path.join(RAW, "evds_2026-10-30")
EVDS_YENI = os.path.join(RAW, "evds_2026-11-01")
TUIK = os.path.join(RAW, "tuik_2026-11-01")

TABLOLAR = {
    1: "tablo_1_krediler",
    2: "tablo_2_mevduat",
    3: "tablo_3_bireysel_bankacilik",
    4: "tablo_4_secilmis_sektorel_krediler",
    5: "tablo_5_oranlar",
    6: "tablo_6_subeler_ve_nufus",
    7: "tablo_7_altin",
}
ANAHTAR = ["plaka", "period"]
META = ["grup_kod", "Yıl", "Ay", "il_adi", "Grup", "table_no"]

_TR = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
                     "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})


def ascii_ad(ad):
    """Türkçe sütun adını snake_case ASCII'ye çevirir."""
    return re.sub(r"[^a-z0-9]+", "_", ad.translate(_TR).lower()).strip("_")


# --------------------------------------------------------------------- FinTürk
def finturk_tablo(no):
    return pd.read_csv(os.path.join(FINTURK, f"{TABLOLAR[no]}.csv"), encoding="utf-8-sig")


def finturk_genis():
    """7 tabloyu (plaka, period) üzerinden birleştirir; sütun adları t<no>_<ascii>."""
    ana = finturk_tablo(1)[ANAHTAR + ["il_adi"]].copy()
    for no in TABLOLAR:
        df = finturk_tablo(no)
        degerler = [c for c in df.columns if c not in META + ANAHTAR]
        df = df[ANAHTAR + degerler].rename(columns={c: f"t{no}_{ascii_ad(c)}" for c in degerler})
        ana = ana.merge(df, on=ANAHTAR, how="left", validate="one_to_one")
    ana["donem"] = pd.PeriodIndex(ana["period"], freq="M").asfreq("Q")
    return ana.sort_values(["plaka", "donem"]).reset_index(drop=True)


# ------------------------------------------------------------------------ TÜFE
def _tuik_tufe_blogu(yol, baslik_satiri, ilk_satir, son_satir):
    x = pd.read_excel(yol, header=None, engine="xlrd")
    assert "Endeks" in str(x.iloc[baslik_satiri, 1]) or "endeks" in str(x.iloc[0, 0]), yol
    blok = x.iloc[ilk_satir:son_satir].set_index(0).iloc[:, :12]
    blok.columns = range(1, 13)
    s = blok.stack()
    s.index = [pd.Period(f"{int(y)}-{m:02d}", "M") for y, m in s.index]
    return pd.to_numeric(s, errors="coerce").dropna().sort_index()


def tufe_zincir(kaydet=True):
    """2010-01'den bugüne tek bir TÜFE endeksi (2025=100).

    Yöntem: TÜİK'in 2025=100 bazlı resmi tablosu (veriportali, "Tüketici fiyat endeksi ve
    değişim oranları") 2005-01'e kadar geriye uzatılmış olarak yayımlanıyor; ana seri budur.
    Doğrulama: eski 2003=100 seri (EVDS TP.FG.J0) ile çakışan 2010-01 → 2026-01 aylarında
    oran sabit olmalı. Ayrıca eski seriyi 2025-12 oranıyla zincirleyip sonrasını yeni serinin
    aylık değişimleriyle uzatan bağımsız bir zincir kurulur ve farkı raporlanır.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yeni = _tuik_tufe_blogu(os.path.join(TUIK, "tufe_tablo_45.xls"), 5, 6, 28)
    evds = pd.read_csv(os.path.join(EVDS, "makro_aylik.csv"), encoding="utf-8-sig")
    eski = pd.Series(evds["tufe"].values, index=pd.PeriodIndex(evds["ay"], freq="M")).dropna()

    df = pd.DataFrame({"tufe_2025_100_tuik": yeni, "tufe_2003_100_evds": eski})
    df = df[df.index >= pd.Period("2010-01", "M")]
    df["oran"] = df["tufe_2025_100_tuik"] / df["tufe_2003_100_evds"]

    # Bağımsız zincir: eski seri 2025-12'ye kadar, çarpan = 2025-12 oranı; sonrası yeni seri değişimleri
    bag = pd.Period("2025-12", "M")
    carpan = df.loc[bag, "oran"]
    zincir = df["tufe_2003_100_evds"] * carpan
    sonra = df.index > bag
    zincir[sonra] = df.loc[bag, "tufe_2025_100_tuik"] * (
        df.loc[sonra, "tufe_2025_100_tuik"] / df.loc[bag, "tufe_2025_100_tuik"])
    df["tufe_zincir_kontrol"] = zincir
    # Üçüncü kaynak: EVDS TP.TUKFIY2025.GENEL (evds_dogrula.py ile 2026-11-01'de indirildi)
    yol = os.path.join(EVDS_YENI, "tufe_yeni_aylik.csv")
    if os.path.exists(yol):
        e = pd.read_csv(yol, encoding="utf-8-sig")
        e.index = pd.PeriodIndex([pd.Period(a, "M") for a in e["ay"]], freq="M")
        df["tufe_2025_100_evds"] = e["tufe_2025_100"]
    df["tufe"] = df["tufe_2025_100_tuik"]
    df.index.name = "ay"
    if kaydet:
        os.makedirs(INTERIM, exist_ok=True)
        df.to_csv(os.path.join(INTERIM, "tufe_zincir.csv"), encoding="utf-8-sig")
    return df


# ------------------------------------------------------------------------ EVDS
def evds_ceyrek(tufe):
    """EVDS çeyreklik makro + zincirlenmiş TÜFE (çeyrek sonu ayı değeri)."""
    aylik = pd.read_csv(os.path.join(EVDS, "makro_aylik.csv"), encoding="utf-8-sig")
    aylik.index = pd.PeriodIndex(aylik.pop("ay"), freq="M")
    aylik = aylik.drop(columns=["tufe"])
    aylik["tufe"] = tufe["tufe"]
    # Not: Ham makro_ceyreklik.csv'de TÜFE "çeyreğin son mevcut ayı" alınmış; 2026Q1 için
    # bu Ocak değeri. Burada çeyrek sonu ayını (Mart, Haziran, ...) açıkça seçiyoruz.
    ceyrek = aylik.index.asfreq("Q")
    q = aylik.groupby(ceyrek).mean()
    q["tufe"] = aylik["tufe"][[p.month % 3 == 0 for p in aylik.index]].groupby(
        lambda p: p.asfreq("Q")).last()
    # Üç ayı tamamlanmamış çeyreklerin ortalaması yanıltıcı: o çeyrekleri boş bırak
    ay_sayisi = aylik["usd_try"].groupby(ceyrek).count()
    q.loc[ay_sayisi < 3, :] = np.nan
    q.index.name = "donem"
    q = q.add_prefix("m_")
    q["m_tufe_yillik"] = q["m_tufe"].pct_change(4) * 100
    q["m_usd_yillik"] = q["m_usd_try"].pct_change(4) * 100
    return q


# ------------------------------------------------------------------------ TÜİK
# Yayım gecikmesi (yıl sonundan sonra, ay). Varsayım: TÜİK'in olağan bülten takvimine göre
# muhafazakâr değerler; tek tek doğrulanamadı (bkz. rapor "Doğrulanamayanlar").
TUIK_GOSTERGELER = {
    # dosya: (kısa ad, düzey, sıklık, yayım gecikmesi ay)
    "ISGD-GK18575-O18504_duzey2.csv": ("issizlik_ibbs2", 2, "yillik", 4),
    "INS-GK055-O006_duzey3.csv": ("konut_satis", 3, "yillik", 2),
    "UHS-GK096-O0011_duzey3.csv": ("kisi_basi_gsyh", 3, "yillik", 12),
    "ADNKS-GK140832-O29009_duzey3.csv": ("net_goc_hizi", 3, "yillik", 3),
    "ULS-GK111403-O12001_duzey3.csv": ("otomobil", 3, "aylik", 2),
}


def il_ibbs():
    m = pd.read_csv(os.path.join(TUIK, "il_ibbs_eslesme.csv"), encoding="utf-8-sig")
    return m.rename(columns={"code": "plaka", "bolgeKodu": "ibbs2", "nutsKodu": "ibbs3"})


def tuik_ceyrek():
    """TÜİK göstergelerini il x çeyrek ızgarasına, yayım gecikmesine saygı ile yerleştirir.

    Yıllık değer Y yılına ait ise ancak (Y yılı sonu + gecikme) ayından sonra biten ilk
    çeyrekten itibaren kullanılabilir; o çeyrekten sonraki yeni değer gelene kadar taşınır.
    """
    eslesme = il_ibbs()
    parcalar = []
    for dosya, (ad, duzey, siklik, gecikme) in TUIK_GOSTERGELER.items():
        df = pd.read_csv(os.path.join(TUIK, dosya), encoding="utf-8-sig", dtype={"code": str})
        df = df.dropna(subset=["deger"])
        if siklik == "yillik":
            ref_ay = pd.PeriodIndex([f"{d}-12" for d in df["date"]], freq="M")
        else:
            # CİP aylık serilerde "YYYY-0" satırı yıllık değerdir ve YYYY-12 ile aynıdır: at
            df = df[~df["date"].str.endswith("-0")]
            ref_ay = pd.PeriodIndex([f"{d.split('-')[0]}-{int(d.split('-')[1]):02d}" for d in df["date"]], freq="M")
        df["kullanilabilir"] = (ref_ay + gecikme).asfreq("Q")
        if duzey == 2:
            df = df.merge(eslesme[["plaka", "ibbs2"]], left_on="code", right_on="ibbs2")
        else:
            df["plaka"] = df["code"].astype(int)
        if siklik == "aylik":
            # Otomobil: yıllık değişim (%) — seviye il büyüklüğünü ölçer, değişim döngüyü
            df["ref"] = ref_ay
            df = df.sort_values("ref")
            df["deger"] = df.groupby("plaka")["deger"].pct_change(12, fill_method=None) * 100
            df = df.dropna(subset=["deger"])
        s = (df.sort_values("kullanilabilir").groupby(["plaka", "kullanilabilir"])["deger"].last()
             .rename(f"tuik_{ad}"))
        parcalar.append(s)
    out = pd.concat(parcalar, axis=1)
    out.index.names = ["plaka", "donem"]
    return out


# ----------------------------------------------------------------- komşuluk
def il_komsuluk(kaydet=True):
    """TÜİK CİP nuts3.json il sınırlarından kara komşuluğu (sınır paylaşan il çiftleri)."""
    from shapely.geometry import shape

    with open(os.path.join(TUIK, "il_sinirlari_duzey3.geojson"), encoding="utf-8") as f:
        doc = json.load(f)
    geo = {}
    for ft in doc["features"]:
        p = ft["properties"]
        g = ft["geometry"]
        if isinstance(g.get("type"), list):
            g["type"] = g["type"][0]
        geo[int(p["duzeyKodu"])] = (p.get("ad") or p.get("name"), shape(g).buffer(0))
    satirlar = []
    kodlar = sorted(geo)
    for i, a in enumerate(kodlar):
        for b in kodlar[i + 1:]:
            ga, gb = geo[a][1], geo[b][1]
            # Sınır çizgileri sadeleştirilmiş olabilir: 100 m tolerans (yaklaşık 0,001 derece)
            if ga.distance(gb) < 1e-3:
                ortak = ga.buffer(1e-3).intersection(gb.buffer(1e-3)).length
                satirlar.append({"plaka": a, "komsu_plaka": b, "ortak_sinir_yaklasik": ortak})
    df = pd.DataFrame(satirlar)
    df = pd.concat([df, df.rename(columns={"plaka": "komsu_plaka", "komsu_plaka": "plaka"})])
    adlar = {k: v[0] for k, v in geo.items()}
    df["il_adi"] = df["plaka"].map(adlar)
    df["komsu_adi"] = df["komsu_plaka"].map(adlar)
    df = df.sort_values(["plaka", "komsu_plaka"])[["plaka", "il_adi", "komsu_plaka", "komsu_adi",
                                                   "ortak_sinir_yaklasik"]]
    if kaydet:
        df.to_csv(os.path.join(INTERIM, "il_komsuluk.csv"), index=False, encoding="utf-8-sig")
    return df


# ------------------------------------------------------------------- panel
TL_SUTUNLARI_ONEK = ("t1_", "t2_", "t3_", "t4_", "t7_")


def panel_kur(kaydet=True):
    tufe = tufe_zincir(kaydet)
    ft = finturk_genis()
    makro = evds_ceyrek(tufe)
    tuik = tuik_ceyrek()

    p = ft.merge(makro, left_on="donem", right_index=True, how="left")
    p = p.merge(tuik, left_on=["plaka", "donem"], right_index=True, how="left")
    p = p.sort_values(["plaka", "donem"])
    tuik_sut = [c for c in p.columns if c.startswith("tuik_")]
    # Yıllık TÜİK değeri bir sonraki yayına kadar geçerli: il içinde ileri taşı (geri taşıma yok)
    p[tuik_sut] = p.groupby("plaka")[tuik_sut].ffill()

    # Reelleştirme: Bin TL tutarlar ve kişi başı TL'ler, 2025 fiyatlarıyla (tufe 2025=100)
    defl = p["m_tufe"] / 100.0
    tl = [c for c in p.columns if c.startswith(TL_SUTUNLARI_ONEK)] + \
         ["t6_kisi_basi_nakdi_kredi", "t6_kisi_basi_takipteki_alacak",
          "t6_kisi_basi_tasarruf_mevduati", "t6_kisi_basi_toplam_mevduat"]
    reel = p[tl].div(defl, axis=0).add_prefix("r_")
    p = pd.concat([p, reel], axis=1)

    # Hedefin temeli: takip oranı (hesaplanan) ve Türkiye (kredi ağırlıklı) takip oranı
    p["npl"] = p["t1_takipteki_alacaklar"] / p["t1_toplam_nakdi_krediler"] * 100
    tr = p.groupby("donem")[["t1_takipteki_alacaklar", "t1_toplam_nakdi_krediler"]].sum()
    p["npl_tr"] = p["donem"].map(tr["t1_takipteki_alacaklar"] / tr["t1_toplam_nakdi_krediler"] * 100)
    p["yil"] = p["donem"].dt.year
    p["period"] = p["period"].astype(str)
    if kaydet:
        out = p.copy()
        out["donem"] = out["donem"].astype(str)
        out.to_parquet(os.path.join(INTERIM, "panel.parquet"), index=False)
    return p


def panel_oku():
    p = pd.read_parquet(os.path.join(INTERIM, "panel.parquet"))
    p["donem"] = pd.PeriodIndex(p["donem"], freq="Q")
    return p
