"""FinTürk veri kalite kontrolleri. Her fonksiyon bir DataFrame döndürür; rapor tabloları buradan."""
import numpy as np
import pandas as pd

from . import data


def anahtar_kontrol():
    satirlar = []
    beklenen_donem = pd.period_range("2010-03", "2026-06", freq="Q")
    for no, ad in data.TABLOLAR.items():
        d = data.finturk_tablo(no)
        donem = d["period"].nunique()
        satirlar.append({
            "tablo": ad,
            "satir": len(d),
            "il": d["plaka"].nunique(),
            "donem": donem,
            "ilk": d["period"].min(),
            "son": d["period"].max(),
            "beklenen_satir": 81 * donem,
            "tekrarlanan_anahtar": int(d.duplicated(["plaka", "period"]).sum()),
            "eksik_donem_(2010-03_sonrasi)": len(beklenen_donem) - donem if no != 7 else "2015-09'dan başlıyor",
            "plaka_basina_tek_il_adi": bool((d.groupby("plaka")["il_adi"].nunique() == 1).all()),
            "il_olmayan_kayit": int((~d["plaka"].between(1, 81)).sum()),
            "grup_kod": ",".join(map(str, d["grup_kod"].unique())),
        })
    return pd.DataFrame(satirlar)


def il_adi_tuik_eslesme():
    """FinTürk il adları ile TÜİK CİP il adlarının plaka üzerinden karşılaştırması."""
    ft = data.finturk_tablo(1).groupby("plaka")["il_adi"].first()
    tu = data.il_ibbs().set_index("plaka")["ad"]
    df = pd.DataFrame({"finturk": ft, "tuik": tu})
    df["ayni"] = df["finturk"] == df["tuik"]
    return df


def muhasebe_kontrol(p):
    fark = p["t1_toplam_nakdi_krediler"] - p["t1_nakdi_krediler"] - p["t1_takipteki_alacaklar"]
    hazir = p["t5_takipteki_alacaklar_toplam_nakdi_kredi_orani"]
    oran_sut = [c for c in p.columns if c.startswith("t5_")]
    oran_aralik = {c: int(((p[c] < 0) | (p[c] > 100)).sum()) for c in oran_sut}
    # Bireysel kredi toplamı toplam nakdi kredinin üstüne çıkmamalı
    bireysel = p[["t3_tasit_kredisi", "t3_konut_kredisi", "t3_kredili_mevduat_hesabi",
                  "t3_diger_tuketici_kredileri", "t3_bireysel_kredi_kartlari"]].sum(axis=1)
    satirlar = [
        {"kontrol": "Toplam = Nakdi + Takipteki (|fark| > 1 Bin TL olan satır)", "sonuc": int((fark.abs() > 1).sum())},
        {"kontrol": "Hesaplanan NPL ile tablo_5 hazır oran arasındaki en büyük fark (puan)",
         "sonuc": round(float((p["npl"] - hazir).abs().max()), 6)},
        {"kontrol": "Kredi/mevduat oranları > 100 (beklenebilir, bilgi amaçlı) satır",
         "sonuc": int((p["t5_toplam_nakdi_kredi_toplam_mevduat_orani"] > 100).sum())},
        {"kontrol": "Takip/performans oranları 0-100 dışında (kredi/mevduat oranları hariç)",
         "sonuc": int(sum(v for k, v in oran_aralik.items() if "mevduat" not in k))},
        {"kontrol": "Bireysel krediler toplamı > toplam nakdi kredi satırı", "sonuc": int((bireysel > p["t1_toplam_nakdi_krediler"]).sum())},
        {"kontrol": "Sıfır toplam nakdi kredi satırı", "sonuc": int((p["t1_toplam_nakdi_krediler"] <= 0).sum())},
        {"kontrol": "Negatif değerli hücre (tüm tablolar)",
         "sonuc": int((p.select_dtypes("number").drop(columns=[c for c in p.columns if c.startswith("m_") or c.startswith("tuik_")]) < 0).sum().sum())},
    ]
    return pd.DataFrame(satirlar)


SEKTOR_ESLESME = {
    # performans oranı sütunu -> (kredi sütunu, takipteki sütunu)
    "t5_denizcilik_kredi_performans_orani": ("t4_denizcilik", "t4_takipteki_denizcilik"),
    "t5_enerji_kredi_performans_orani": ("t4_enerji", "t4_takipteki_enerji"),
    "t5_finansal_kuruluslar_kredi_performans_orani": ("t4_finansal_kuruluslar", "t4_takipteki_finansal_kuruluslar"),
    "t5_metal_ve_islenmis_maden_kredi_performans_orani": ("t4_metal_ve_islenmis_maden", "t4_takipteki_metal_ve_islenmis_maden"),
}


def bos_deger_nedeni(p):
    satirlar = []
    for oran, (kredi, takip) in SEKTOR_ESLESME.items():
        bos = p[oran].isna()
        payda = p[kredi] + p[takip]
        satirlar.append({
            "sutun": oran,
            "bos": int(bos.sum()),
            "bos_ve_kredi+takipteki=0": int((bos & (payda == 0)).sum()),
            "bos_ve_kredi>0": int((bos & (payda > 0)).sum()),
            "bos_olan_il_sayisi": int(p.loc[bos, "plaka"].nunique()),
        })
    return pd.DataFrame(satirlar)


def sicrama_kontrol(p, esik_yuzde=99.5):
    """İl bazında çeyreklik değişimde üst %0,5 dilim. Aynı dönemde çok il sıçrıyorsa tanım değişikliği şüphesi."""
    d = p.sort_values(["plaka", "donem"]).copy()
    seriler = {
        "npl_degisim_puan": d.groupby("plaka")["npl"].diff(),
        "kredi_log_degisim": np.log(d["t1_toplam_nakdi_krediler"]).groupby(d["plaka"]).diff(),
        "takipteki_log_degisim": np.log(d["t1_takipteki_alacaklar"].clip(lower=1)).groupby(d["plaka"]).diff(),
        "mevduat_log_degisim": np.log(d["t2_toplam_mevduat"]).groupby(d["plaka"]).diff(),
    }
    satirlar, detay = [], []
    for ad, s in seriler.items():
        a = s.abs()
        esik = np.nanpercentile(a, esik_yuzde)
        uc = d.loc[a > esik, ["plaka", "il_adi", "period"]].assign(seri=ad, deger=s[a > esik])
        detay.append(uc)
        donem_say = uc["period"].value_counts()
        satirlar.append({
            "seri": ad,
            "esik_(mutlak)": round(float(esik), 4),
            "uc_gozlem": len(uc),
            "en_cok_uc_donem": ", ".join(f"{k} ({v})" for k, v in donem_say.head(4).items()),
        })
    return pd.DataFrame(satirlar), pd.concat(detay)


def tr_toplam_sicrama(p):
    """Türkiye toplamında çeyreklik değişim: tanım değişikliği tüm illeri aynı anda etkiler."""
    tr = p.groupby("period")[["t1_toplam_nakdi_krediler", "t1_takipteki_alacaklar", "t2_toplam_mevduat"]].sum()
    tr["npl_tr"] = tr["t1_takipteki_alacaklar"] / tr["t1_toplam_nakdi_krediler"] * 100
    out = pd.DataFrame({
        "kredi_q_degisim_%": tr["t1_toplam_nakdi_krediler"].pct_change() * 100,
        "takipteki_q_degisim_%": tr["t1_takipteki_alacaklar"].pct_change() * 100,
        "npl_tr": tr["npl_tr"],
        "npl_tr_q_degisim": tr["npl_tr"].diff(),
    })
    return out


def revizyon_kontrol(klasor):
    """Yeniden indirilen dönemleri 30 Ekim indirmesiyle hücre hücre karşılaştırır."""
    import glob
    import os

    satirlar = []
    for yol in sorted(glob.glob(os.path.join(klasor, "tablo_*.csv"))):
        yeni = pd.read_csv(yol, encoding="utf-8-sig")
        no = int(os.path.basename(yol).split("_")[1])
        eski = data.finturk_tablo(no)
        sut = [c for c in yeni.columns if c not in data.META + data.ANAHTAR]
        m = eski.merge(yeni, on=data.ANAHTAR, suffixes=("_eski", "_yeni"))
        for donem, g in m.groupby("period"):
            fark_hucre, en_buyuk = 0, 0.0
            for c in sut:
                a, b = g[f"{c}_eski"], g[f"{c}_yeni"]
                f = (a - b).abs()
                ayni_bos = a.isna() & b.isna()
                fark = (f > 1e-6) | (a.isna() != b.isna())
                fark_hucre += int((fark & ~ayni_bos).sum())
                en_buyuk = max(en_buyuk, float(f.max(skipna=True) or 0))
            satirlar.append({"tablo": no, "period": donem, "il": len(g), "sutun": len(sut),
                             "farkli_hucre": fark_hucre, "en_buyuk_mutlak_fark": en_buyuk})
    return pd.DataFrame(satirlar)
