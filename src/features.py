"""Özellikler: yalnızca t çeyreğinde (ve öncesinde) bilinen bilgiyle.

Varsayım: Tahmin, FinTürk'te t çeyreği yayımlandığında yapılır (yayım gecikmesi yaklaşık 2-3 ay,
doğrulanamadı). Bu anda t'ye kadar olan makro veri de bilinir. TÜİK göstergeleri
data.tuik_ceyrek() içinde yayım gecikmesiyle kaydırıldı.
"""
import numpy as np
import pandas as pd

from . import data

SEKTORLER = ["gida_mesrubat_ve_tutun", "insaat", "metal_ve_islenmis_maden", "finansal_kuruluslar",
             "tekstil_ve_tekstil_urunleri", "toptan_ticaret_ve_komisyonculuk", "turizm",
             "ziraat_ve_balikcilik", "enerji", "denizcilik"]
BIREYSEL = ["tasit_kredisi", "konut_kredisi", "kredili_mevduat_hesabi", "diger_tuketici_kredileri",
            "bireysel_kredi_kartlari"]


def _g(p, s):
    return p.groupby("plaka")[s]


def ozellik_uret(p):
    p = p.sort_values(["plaka", "donem"]).copy()
    f = pd.DataFrame(index=p.index)
    kredi = p["t1_toplam_nakdi_krediler"]

    # --- FinTürk: NPL düzeyi, gecikmeleri ve değişimleri
    f["npl"] = p["npl"]
    for k in (1, 2, 4, 8):
        f[f"npl_l{k}"] = _g(p, "npl").shift(k)
        f[f"d_npl_{k}"] = p["npl"] - f[f"npl_l{k}"]
    f["npl_eksi_tr"] = p["npl"] - p["npl_tr"]
    f["d_npl_tr_4"] = p["npl_tr"] - _g(p, "npl_tr").shift(4)
    f["d_npl_4_goreli"] = f["d_npl_4"] - f["d_npl_tr_4"]
    f["npl_il_ort_sapma"] = p["npl"] - _g(p, "npl").transform(lambda s: s.expanding().mean())

    # --- büyüme (reel)
    for s, ad in [("r_t1_toplam_nakdi_krediler", "kredi"), ("r_t2_toplam_mevduat", "mevduat"),
                  ("r_t1_takipteki_alacaklar", "takipteki")]:
        ls = np.log(p[s].clip(lower=1))
        f[f"{ad}_reel_b4"] = ls - ls.groupby(p["plaka"]).shift(4)
        f[f"{ad}_reel_b1"] = ls - ls.groupby(p["plaka"]).shift(1)
    f["kredi_reel_b4_eksi_tr"] = f["kredi_reel_b4"] - f.groupby(p["donem"])["kredi_reel_b4"].transform("median")

    # --- oranlar
    f["kredi_mevduat"] = p["t5_toplam_nakdi_kredi_toplam_mevduat_orani"]
    f["gayrinakdi_nakdi"] = p["t1_gayrinakdi_krediler"] / kredi
    f["dth_payi"] = (p["t2_tasarruf_mevduati_dth"] + p["t2_diger_mevduat_dth"]) / p["t2_toplam_mevduat"]

    # --- bireysel kredi payları ve kendi takip oranları
    for b in BIREYSEL:
        f[f"pay_{b}"] = p[f"t3_{b}"] / kredi
    f["pay_bireysel"] = sum(p[f"t3_{b}"] for b in BIREYSEL) / kredi
    for b in ("konut_kredisi", "tasit_kredisi", "diger_tuketici_kredileri"):
        kod = {"konut_kredisi": "konut_kredisi", "tasit_kredisi": "tasit_kredisi",
               "diger_tuketici_kredileri": "diger_tuketici_kredileri"}[b]
        f[f"perf_{b}"] = p[f"t5_{kod}_performans_orani"]
    f["kk_takip_orani"] = p["t4_takipteki_kredi_kartlari"] / (p["t3_bireysel_kredi_kartlari"] + p["t4_takipteki_kredi_kartlari"])

    # --- sektörel paylar ve sektörel takip oranları
    for s in SEKTORLER:
        f[f"pay_{s}"] = p[f"t4_{s}"] / kredi
    perf = [c for c in p.columns if c.startswith("t5_") and "performans" in c
            and not any(b in c for b in ("konut", "tasit", "diger_tuketici"))]
    for c in perf:
        f["perf_" + c[3:].replace("_kredi_performans_orani", "").replace("_kredi_performans_oran", "")] = p[c]
    # yoğunlaşma: en büyük sektör payı (tek büyük borçlu riski için kaba vekil)
    f["sektor_max_pay"] = f[[f"pay_{s}" for s in SEKTORLER]].max(axis=1)

    # --- kişi başı / ölçek
    f["log_kisi_basi_kredi_reel"] = np.log(p["r_t6_kisi_basi_nakdi_kredi"])
    f["log_kisi_basi_mevduat_reel"] = np.log(p["r_t6_kisi_basi_toplam_mevduat"])
    f["subeye_dusen_nufus"] = p["t6_subeye_dusen_nufus"]
    f["log_kredi_reel"] = np.log(p["r_t1_toplam_nakdi_krediler"])

    # --- EVDS makro (illerde ortak)
    for c in ["m_tufe_yillik", "m_usd_yillik", "m_fonlama_faizi", "m_ihtiyac_faizi", "m_konut_faizi",
              "m_tuketici_faizi"]:
        f[c] = p[c]
    f["m_reel_ihtiyac_faizi"] = p["m_ihtiyac_faizi"] - p["m_tufe_yillik"]
    f["m_d_ihtiyac_faizi_4"] = p["m_ihtiyac_faizi"] - _g(p, "m_ihtiyac_faizi").shift(4)

    # --- TÜİK
    f["tuik_issizlik_ibbs2"] = p["tuik_issizlik_ibbs2"]
    f["tuik_konut_satis_b4"] = np.log(p["tuik_konut_satis"]) - np.log(_g(p, "tuik_konut_satis").shift(4))
    f["tuik_kisi_basi_gsyh_reel_log"] = np.log(p["tuik_kisi_basi_gsyh"] / p["m_tufe"])
    f["tuik_net_goc_hizi"] = p["tuik_net_goc_hizi"]
    f["tuik_otomobil_yillik"] = p["tuik_otomobil"]
    f = f.replace([np.inf, -np.inf], np.nan)
    return f


def komsu_ozellik(p, f, komsuluk=None):
    """Komşu illerin t anındaki ortalama ΔNPL4 ve NPL düzeyi (kara komşuluğu)."""
    if komsuluk is None:
        komsuluk = pd.read_csv(f"{data.INTERIM}/il_komsuluk.csv", encoding="utf-8-sig")
    tab = pd.DataFrame({"plaka": p["plaka"], "donem": p["donem"], "d_npl_4": f["d_npl_4"],
                        "npl": f["npl"], "d_npl_1": f["d_npl_1"]})
    m = komsuluk[["plaka", "komsu_plaka"]].merge(
        tab.rename(columns={"plaka": "komsu_plaka"}), on="komsu_plaka")
    ort = m.groupby(["plaka", "donem"])[["d_npl_4", "npl", "d_npl_1"]].mean().add_prefix("komsu_")
    out = tab[["plaka", "donem"]].merge(ort, left_on=["plaka", "donem"], right_index=True, how="left")
    out.index = p.index
    out = out.drop(columns=["plaka", "donem"])
    out["komsu_d_npl_4_fark"] = f["d_npl_4"] - out["komsu_d_npl_4"]
    return out


def gruplar(f):
    """Ablation için özellik grupları."""
    tum = list(f.columns)
    makro = [c for c in tum if c.startswith("m_")]
    tuik = [c for c in tum if c.startswith("tuik_")]
    komsu = [c for c in tum if c.startswith("komsu_")]
    finturk = [c for c in tum if c not in makro + tuik + komsu]
    return {
        "i_finturk": finturk,
        "ii_+evds": finturk + makro,
        "iii_+komsu": finturk + makro + komsu,
        "iv_+tuik": finturk + makro + komsu + tuik,
    }
