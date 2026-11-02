"""Etiket tanımları (E1-E5) ve etiket analizleri.

Hepsi t çeyreğindeki il için t+4'teki duruma bakar; son 4 çeyrekte (t+4 henüz yok) etiket NaN.
"""
import numpy as np
import pandas as pd

UFUK = 4
E1_ESIKLER = [0.25, 0.5, 1.0]
E2_ESIKLER = [0.25, 0.5, 1.0]
E3_DILIM = 0.20


def ileri(p, sutun, k=UFUK):
    return p.groupby("plaka")[sutun].shift(-k)


def etiketle(p):
    """Paneli (plaka, donem sıralı) alır, etiket sütunlarını ekleyip döndürür."""
    p = p.sort_values(["plaka", "donem"]).copy()
    p["dnpl4"] = ileri(p, "npl") - p["npl"]
    p["dnpl4_tr"] = ileri(p, "npl_tr") - p["npl_tr"]
    p["dnpl4_goreli"] = p["dnpl4"] - p["dnpl4_tr"]
    var = p["dnpl4"].notna()
    for e in E1_ESIKLER:
        p[f"E1_{e}"] = (p["dnpl4"] >= e).astype(float).where(var)
    for e in E2_ESIKLER:
        p[f"E2_{e}"] = (p["dnpl4_goreli"] >= e).astype(float).where(var)
    # E3: her çeyrekte ΔNPL4'e göre en kötü %20 (eşitlikte yukarı yuvarlanan sıra)
    sira = p.groupby("donem")["dnpl4"].rank(ascending=False, method="first", pct=True)
    p["E3"] = (sira <= E3_DILIM).astype(float).where(var)
    # E5: takipteki tutarın 4 çeyreklik reel log-değişimi (paydadan bağımsız)
    lt = np.log(p["r_t1_takipteki_alacaklar"].clip(lower=1))
    p["E5_reel_takip_log4"] = ileri(p.assign(_lt=lt), "_lt") - lt
    lt_tr = np.log(p.groupby("donem")["r_t1_takipteki_alacaklar"].transform("sum"))
    p["E5_goreli"] = p["E5_reel_takip_log4"] - (ileri(p.assign(_l=lt_tr), "_l") - lt_tr)
    return p


IKILI = [f"E1_{e}" for e in E1_ESIKLER] + [f"E2_{e}" for e in E2_ESIKLER] + ["E3"]


def pozitif_ozet(p):
    """Her ikili etiket için toplam ve yıllara göre pozitif oranı, il başına pozitif sayısı."""
    d = p.dropna(subset=["dnpl4"])
    toplam = pd.DataFrame({
        "etiket": IKILI,
        "n": [int(d[e].notna().sum()) for e in IKILI],
        "pozitif": [int(d[e].sum()) for e in IKILI],
        "pozitif_oran": [round(d[e].mean(), 3) for e in IKILI],
        "hic_pozitifi_olmayan_il": [int((d.groupby("plaka")[e].sum() == 0).sum()) for e in IKILI],
        "il_basi_pozitif_medyan": [float(d.groupby("plaka")[e].sum().median()) for e in IKILI],
        "yil_oran_min": [round(d.groupby("yil")[e].mean().min(), 3) for e in IKILI],
        "yil_oran_max": [round(d.groupby("yil")[e].mean().max(), 3) for e in IKILI],
        "oran_%10-40_arasi_yil": [int(d.groupby("yil")[e].mean().between(0.10, 0.40).sum()) for e in IKILI],
        "tek_sinifa_yakin_yil_(<%5_veya_>%95)": [
            int(((d.groupby("yil")[e].mean() < 0.05) | (d.groupby("yil")[e].mean() > 0.95)).sum()) for e in IKILI],
    })
    yillik = d.groupby("yil")[IKILI].mean().round(3)
    yillik.insert(0, "n", d.groupby("yil").size())
    return toplam, yillik


def varyans_ayristirma(p, hedef="dnpl4"):
    """İki yönlü sabit etki ayrıştırması: R² (çeyrek FE), R² (il FE), R² (ikisi, dengeli panelde toplamsal)."""
    d = p.dropna(subset=[hedef])[["plaka", "donem", hedef]]
    y = d[hedef]
    tss = ((y - y.mean()) ** 2).sum()
    q = d.groupby("donem")[hedef].transform("mean")
    i = d.groupby("plaka")[hedef].transform("mean")
    r2_q = 1 - ((y - q) ** 2).sum() / tss
    r2_i = 1 - ((y - i) ** 2).sum() / tss
    iki = q + i - y.mean()  # dengeli panelde iki yönlü FE tahmini
    r2_qi = 1 - ((y - iki) ** 2).sum() / tss
    return {"hedef": hedef, "n": len(d), "R2_ceyrek_FE": round(r2_q, 3), "R2_il_FE": round(r2_i, 3),
            "R2_iki_yonlu": round(r2_qi, 3), "kalan_(il-ceyrek_etkilesimi)": round(1 - r2_qi, 3),
            "std": round(float(y.std()), 3)}


def payda_etkisi(p):
    """Takipteki tutar (reel) artarken oran düşen il-çeyrekler: büyüme paydayı şişiriyor."""
    d = p.sort_values(["plaka", "donem"]).copy()
    g = d.groupby("plaka")
    takip_art = g["r_t1_takipteki_alacaklar"].diff(4) > 0
    oran_dus = g["npl"].diff(4) < 0
    kredi_buyume = g["r_t1_toplam_nakdi_krediler"].pct_change(4, fill_method=None) * 100
    gecerli = g["npl"].diff(4).notna()
    maske = takip_art & oran_dus & gecerli
    yillik = maske[gecerli].groupby(d.loc[gecerli, "yil"]).mean().round(3)
    ozet = {
        "gecerli_il_ceyrek": int(gecerli.sum()),
        "takipteki_reel_artan_ama_oran_dusen": int(maske.sum()),
        "oran": round(float(maske[gecerli].mean()), 3),
        "bu_gozlemlerde_medyan_reel_kredi_buyumesi_%": round(float(kredi_buyume[maske].median()), 1),
        "diger_gozlemlerde_medyan_reel_kredi_buyumesi_%": round(float(kredi_buyume[~maske & gecerli].median()), 1),
    }
    return ozet, yillik
