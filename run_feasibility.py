"""
İl bazında kredi riski erken uyarı: fizibilite deneyi (tek komut).
Çalıştır:  source .venv/bin/activate && python run_feasibility.py
Girdi:     data/raw/ altındaki FinTürk, EVDS ve TÜİK indirmeleri (salt okunur)
Çıktı:     data/interim/{panel.parquet, tufe_zincir.csv, il_komsuluk.csv}
           reports/tablolar/*.csv, reports/figures/*.png, reports/tablolar/ozet.json
"""
import json
import os
import time
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd

from src import data, evaluate as E, features as F, figures as G, kalite, labels as L

np.random.seed(E.TOHUM)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
TAB = os.path.join("reports", "tablolar")
FIG = os.path.join("reports", "figures")
os.makedirs(TAB, exist_ok=True)

ANA_ETIKET = "E3"                       # ana öneri (bkz. rapor bölüm 5)
IKILI_ETIKETLER = ["E3", "E2_0.5", "E1_0.5"]
SUREKLI_HEDEFLER = ["dnpl4", "dnpl4_goreli"]
ozet = {}
sure = {}


def adim(ad):
    def sar(fn):
        def calistir():
            t = time.time()
            print(f"\n=== {ad}", flush=True)
            r = fn()
            sure[ad] = round(time.time() - t, 1)
            print(f"    ({sure[ad]} s)", flush=True)
            return r
        return calistir
    return sar


@adim("1. Panel, TÜFE zinciri, komşuluk")
def panel():
    os.makedirs(data.INTERIM, exist_ok=True)
    kom = data.il_komsuluk()
    p = data.panel_kur()
    t = data.tufe_zincir(kaydet=False)
    ozet["tufe"] = {
        "cakisan_ay": int(t["oran"].notna().sum()),
        "oran_cv": float(t["oran"].std() / t["oran"].mean()),
        "zincir_kontrol_max_fark_%": float(((t["tufe_zincir_kontrol"] / t["tufe"] - 1).abs().max()) * 100),
        "evds_tuik_max_fark": float((t["tufe_2025_100_evds"] - t["tufe_2025_100_tuik"]).abs().max()),
        "ilk": str(t.index.min()), "son": str(t.index.max()),
    }
    ozet["komsuluk"] = {"cift": len(kom) // 2, "il": int(kom["plaka"].nunique()),
                        "min_komsu": int(kom.groupby("plaka").size().min()),
                        "max_komsu": int(kom.groupby("plaka").size().max())}
    ozet["panel"] = {"satir": len(p), "sutun": p.shape[1]}
    return p


p = panel()


@adim("2. Kalite kontrolleri")
def kalite_adimi():
    kalite.anahtar_kontrol().to_csv(f"{TAB}/kalite_anahtar.csv", index=False)
    kalite.il_adi_tuik_eslesme().to_csv(f"{TAB}/kalite_il_adi_tuik.csv")
    kalite.muhasebe_kontrol(p).to_csv(f"{TAB}/kalite_muhasebe.csv", index=False)
    kalite.bos_deger_nedeni(p).to_csv(f"{TAB}/kalite_bos_deger.csv", index=False)
    s, detay = kalite.sicrama_kontrol(p)
    s.to_csv(f"{TAB}/kalite_sicrama_ozet.csv", index=False)
    detay.to_csv(f"{TAB}/kalite_sicrama_detay.csv", index=False)
    kalite.tr_toplam_sicrama(p).to_csv(f"{TAB}/kalite_tr_toplam.csv")
    rev = os.path.join(data.RAW, "finturk_2026-11-01_revizyon_kontrol")
    if os.path.isdir(rev):
        kalite.revizyon_kontrol(rev).to_csv(f"{TAB}/kalite_revizyon.csv", index=False)


kalite_adimi()


@adim("3. Etiketler")
def etiket_adimi():
    q = L.etiketle(p)
    toplam, yillik = L.pozitif_ozet(q)
    toplam.to_csv(f"{TAB}/etiket_ozet.csv", index=False)
    yillik.to_csv(f"{TAB}/etiket_yillik.csv")
    il = q.dropna(subset=["dnpl4"]).groupby("il_adi")[L.IKILI].sum().astype(int)
    il.to_csv(f"{TAB}/etiket_il_pozitif_sayisi.csv")
    var = pd.DataFrame([L.varyans_ayristirma(q, h) for h in
                        ["dnpl4", "dnpl4_goreli", "E5_reel_takip_log4", "E5_goreli"]])
    var.to_csv(f"{TAB}/varyans_ayristirma.csv", index=False)
    pay, pay_yil = L.payda_etkisi(q)
    pay_yil.to_csv(f"{TAB}/payda_etkisi_yillik.csv")
    ozet["payda_etkisi"] = pay
    for e in ["E1_0.5", "E2_0.5", "E3", "E1_1.0"]:
        G.etiket_isi_haritasi(q, e, FIG)
    G.pozitif_oran_yillik(yillik, FIG)
    G.npl_dagilim(q, FIG)
    G.varyans_grafik(var, FIG)
    return q


p = etiket_adimi()


@adim("4. Özellikler")
def ozellik_adimi():
    f = F.ozellik_uret(p)
    f = pd.concat([f, F.komsu_ozellik(p, f)], axis=1)
    f.isna().mean().round(3).rename("bos_oran").to_csv(f"{TAB}/ozellik_bos_oran.csv")
    return f


f = ozellik_adimi()
grp = F.gruplar(f)
ozet["ozellik_sayisi"] = {k: len(v) for k, v in grp.items()}


@adim("5. İkili deneyler (3 etiket x 4 özellik seti)")
def ikili_adimi():
    tum_tah, tum_ozet = [], []
    for e in IKILI_ETIKETLER:
        b1 = f["d_npl_4"] if e.startswith("E1") else f["d_npl_4_goreli"]
        for s, cols in grp.items():
            t = time.time()
            tah = E.ikili_deney(f[cols], p[e], p["donem"], b1, e, s)
            oz = E.ikili_ozet(tah).assign(etiket=e, set=s)
            tum_tah.append(tah)
            tum_ozet.append(oz)
            top = oz[(oz["test_yili"] == "TOPLAM") & (oz["model"] == "B3_LGBM")].iloc[0]
            print(f"    {e:7} {s:11} LGBM PR-AUC={top['PR_AUC']:.3f} ROC={top['ROC_AUC']:.3f} "
                  f"({time.time() - t:.0f} s)")
    tah = pd.concat(tum_tah)
    oz = pd.concat(tum_ozet)
    tah.assign(donem=tah["donem"].astype(str)).to_csv(f"{TAB}/tahminler_ikili.csv")
    oz.to_csv(f"{TAB}/metrik_ikili.csv", index=False)
    return oz


oz = ikili_adimi()


@adim("6. Sürekli hedef (E4)")
def surekli_adimi():
    sonuc = []
    for h in SUREKLI_HEDEFLER:
        b1 = f["d_npl_4"] if h == "dnpl4" else f["d_npl_4_goreli"]
        for s in ["i_finturk", "iv_+tuik"]:
            tah = E.surekli_deney(f[grp[s]], p[h], p["donem"], b1, h, s)
            sonuc.append(E.surekli_ozet(tah).assign(hedef=h, set=s))
    r = pd.concat(sonuc)
    r.to_csv(f"{TAB}/metrik_surekli.csv", index=False)
    return r


sur = surekli_adimi()


@adim("7. Özet tablolar ve şekiller")
def ozet_adimi():
    top = oz[oz["test_yili"] == "TOPLAM"]
    abl = top[top["model"] == "B3_LGBM"][["etiket", "set", "PR_AUC", "ROC_AUC", "Brier", "P@10"]].copy()
    b1 = top[(top["model"] == "B1")].drop_duplicates("etiket").set_index("etiket")
    for m in ["PR_AUC", "ROC_AUC", "P@10"]:
        abl[f"B1_{m}"] = abl["etiket"].map(b1[m])
    abl.to_csv(f"{TAB}/ablation.csv", index=False)
    G.ablation_grafik(abl, "PR_AUC", FIG)
    G.ablation_grafik(abl, "P@10", FIG)
    for e in IKILI_ETIKETLER:
        d = oz[(oz["etiket"] == e) & (oz["set"] == "iv_+tuik")]
        G.model_metrik_yillik(d, e, "PR_AUC", FIG)
    # Yıl bazında LGBM'in B1'i geçtiği yıl sayısı (set iv)
    kazanc = {}
    for e in IKILI_ETIKETLER:
        d = oz[(oz["etiket"] == e) & (oz["set"] == "iv_+tuik") & (oz["test_yili"] != "TOPLAM")]
        w = d.pivot(index="test_yili", columns="model", values="PR_AUC").dropna()
        kazanc[e] = {"yil": len(w), "lgbm>b1": int((w["B3_LGBM"] > w["B1"]).sum()),
                     "lgbm>lr": int((w["B3_LGBM"] > w["B2_LR"]).sum())}
    ozet["yil_bazinda_kazanc"] = kazanc


ozet_adimi()


@adim("8. Sızıntı denetimi: önem sıralaması (son kat, ana etiket, set iv)")
def sizinti_adimi():
    import shap

    cols = grp["iv_+tuik"]
    y = p[ANA_ETIKET]
    son_yil, eg, te = list(E.katlar(p["donem"]))[-1]
    eg = eg & y.notna()
    prm = E.lgb_ara(f.loc[eg, cols], y[eg].astype(int), p.loc[eg, "donem"])
    m = lgb.LGBMClassifier(**prm, **E.LGB_SABIT).fit(f.loc[eg, cols], y[eg].astype(int))
    gain = pd.Series(m.booster_.feature_importance("gain"), index=cols)
    sv = shap.TreeExplainer(m).shap_values(f.loc[te & y.notna(), cols])
    sv = sv[1] if isinstance(sv, list) else sv
    sh = pd.Series(np.abs(sv).mean(axis=0), index=cols)
    imp = pd.DataFrame({"gain": gain, "gain_pay": gain / gain.sum(), "shap_ort_mutlak": sh})
    imp = imp.sort_values("gain", ascending=False)
    imp.head(25).to_csv(f"{TAB}/onem_top25.csv")
    ozet["sizinti_kat"] = {"test_yili": son_yil, "egitim_n": int(eg.sum()), "parametre": prm}


sizinti_adimi()

ozet["sure_s"] = sure
with open(f"{TAB}/ozet.json", "w", encoding="utf-8") as fh:
    json.dump(ozet, fh, ensure_ascii=False, indent=2, default=str)
print("\nBitti. Tablolar:", TAB, " Şekiller:", FIG)
