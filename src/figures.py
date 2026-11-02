"""Rapor şekilleri (PNG). Renkler: dataviz referans paleti (mavi, turuncu, aqua, sarı)."""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

RENK = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
MUREKKEP, IKINCIL, ZEMIN = "#0b0b0b", "#52514e", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": ZEMIN, "axes.facecolor": ZEMIN, "axes.edgecolor": IKINCIL,
    "axes.labelcolor": MUREKKEP, "xtick.color": IKINCIL, "ytick.color": IKINCIL,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#e6e5e0", "grid.linewidth": 0.6, "font.size": 10, "lines.linewidth": 2,
})


def _kaydet(fig, klasor, ad):
    os.makedirs(klasor, exist_ok=True)
    fig.savefig(os.path.join(klasor, ad), dpi=150, bbox_inches="tight")
    plt.close(fig)


def etiket_isi_haritasi(p, etiket, klasor):
    """Yıl x il ısı haritası: hücre = o yıldaki 4 çeyreğin kaçında etiket 1 (0-4)."""
    d = p.dropna(subset=[etiket])
    tab = d.groupby(["il_adi", "yil"])[etiket].mean().unstack()
    sira = d.groupby("il_adi")[etiket].mean().sort_values(ascending=False).index
    tab = tab.loc[sira]
    fig, ax = plt.subplots(figsize=(8, 15))
    cmap = ListedColormap(["#f0efec", "#cde2fb", "#86b6ef", "#3987e5", "#184f95"])
    im = ax.imshow(np.round(tab.values * 4), aspect="auto", cmap=cmap, vmin=-0.5, vmax=4.5)
    ax.set_xticks(range(tab.shape[1]), tab.columns, rotation=90)
    ax.set_yticks(range(tab.shape[0]), tab.index, fontsize=6.5)
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, ticks=range(5), shrink=0.4)
    cb.set_label("Yıl içinde pozitif çeyrek sayısı")
    ax.set_title(f"{etiket}: il x yıl pozitif etiket (iller ortalama orana göre sıralı)", loc="left")
    ax.set_xlabel("Yıl (t çeyreğinin yılı)")
    _kaydet(fig, klasor, f"isi_haritasi_{etiket}.png")


def pozitif_oran_yillik(yillik, klasor):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for renk, (e, ad) in zip(RENK, [("E1_0.5", "E1 mutlak ≥0,5 puan"), ("E2_0.5", "E2 göreli ≥0,5 puan"),
                                     ("E3", "E3 en kötü %20"), ("E1_1.0", "E1 mutlak ≥1,0 puan")]):
        ax.plot(yillik.index, yillik[e] * 100, marker="o", ms=4, color=renk, label=ad)
    ax.axhspan(10, 40, color="#f0efec", zorder=0, label="Hedef aralık %10-40")
    ax.set_ylabel("Pozitif oranı (%)")
    ax.set_xlabel("Yıl (t çeyreğinin yılı; 2025 yalnızca Q1-Q2)")
    ax.set_title("Etiket tanımlarına göre yıllık pozitif oranı", loc="left")
    ax.legend(frameon=False, ncol=2, fontsize=9)
    _kaydet(fig, klasor, "pozitif_oran_yillik.png")


def npl_dagilim(p, klasor):
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
    ax = axs[0]
    q = p.groupby("donem")["npl"].quantile([0.1, 0.5, 0.9]).unstack()
    x = q.index.to_timestamp()
    ax.fill_between(x, q[0.1], q[0.9], color="#cde2fb", label="İller %10-%90 aralığı")
    ax.plot(x, q[0.5], color=RENK[0], label="İl medyanı")
    tr = p.groupby("donem")["npl_tr"].first()
    ax.plot(x, tr.values, color=RENK[1], label="Türkiye (kredi ağırlıklı)")
    ax.set_ylabel("Takip oranı (%)")
    ax.set_title("NPL: il dağılımı ve Türkiye", loc="left")
    ax.legend(frameon=False, fontsize=9)
    ax = axs[1]
    d = p["dnpl4"].dropna().clip(-6, 6)
    ax.hist(d, bins=80, color=RENK[0], edgecolor=ZEMIN, linewidth=0.5)
    for e in (0.25, 0.5, 1.0):
        ax.axvline(e, color=IKINCIL, linewidth=1, linestyle="--")
    ax.set_xlabel("ΔNPL₄ = NPL(t+4) − NPL(t), puan (±6'da kırpıldı)")
    ax.set_ylabel("İl-çeyrek sayısı")
    ax.set_title("4 çeyreklik NPL değişimi dağılımı (kesikli: 0,25/0,5/1,0)", loc="left")
    _kaydet(fig, klasor, "npl_dagilim.png")


def varyans_grafik(var_tablo, klasor):
    fig, ax = plt.subplots(figsize=(8, 3.5))
    v = var_tablo.set_index("hedef")
    y = np.arange(len(v))
    ax.barh(y, v["R2_ceyrek_FE"], color=RENK[0], label="Çeyrek (ülke döngüsü)", height=0.6)
    ax.barh(y, v["R2_iki_yonlu"] - v["R2_ceyrek_FE"], left=v["R2_ceyrek_FE"], color=RENK[1],
            label="İl sabit etkisi", height=0.6)
    ax.barh(y, 1 - v["R2_iki_yonlu"], left=v["R2_iki_yonlu"], color="#d9d8d3",
            label="İl x çeyrek (öğrenilecek sinyal + gürültü)", height=0.6)
    ax.set_yticks(y, v.index)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Varyans payı")
    ax.set_title("Hedef varyansının ayrıştırılması", loc="left")
    ax.legend(frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, -0.55), ncol=3)
    ax.grid(axis="y", visible=False)
    _kaydet(fig, klasor, "varyans_ayristirma.png")


def model_metrik_yillik(ozet, etiket, metrik, klasor):
    d = ozet[(ozet["test_yili"] != "TOPLAM")]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for renk, m in zip(RENK, ["B0", "B1", "B2_LR", "B3_LGBM"]):
        g = d[d["model"] == m]
        ax.plot(g["test_yili"].astype(int), g[metrik], marker="o", ms=4, color=renk, label=m)
    ax.set_xlabel("Test yılı")
    ax.set_ylabel(metrik)
    ax.set_title(f"{etiket}: test yılına göre {metrik} (özellik seti iv)", loc="left")
    ax.legend(frameon=False, ncol=4, fontsize=9)
    _kaydet(fig, klasor, f"model_{etiket}_{metrik}.png")


def ablation_grafik(abl, metrik, klasor):
    fig, ax = plt.subplots(figsize=(9, 4))
    etiketler = list(abl["etiket"].unique())
    setler = list(abl["set"].unique())
    w = 0.8 / len(setler)
    for i, (renk, s) in enumerate(zip(RENK, setler)):
        g = abl[abl["set"] == s].set_index("etiket").loc[etiketler]
        ax.bar(np.arange(len(etiketler)) + i * w, g[metrik], width=w * 0.92, color=renk, label=s)
    b1 = abl.drop_duplicates("etiket").set_index("etiket").loc[etiketler, f"B1_{metrik}"]
    ax.scatter(np.arange(len(etiketler)) + 0.4 - w / 2, b1, marker="_", s=2500, linewidths=2.5, color=MUREKKEP,
               label="B1 kuralı", zorder=3)
    ax.set_xticks(np.arange(len(etiketler)) + 0.4 - w / 2, etiketler)
    ax.set_ylabel(f"LightGBM {metrik} (toplam)")
    ax.set_title(f"Ablation: özellik setine göre LightGBM {metrik}", loc="left")
    ax.legend(frameon=False, fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.1), markerscale=0.3)
    ax.grid(axis="x", visible=False)
    _kaydet(fig, klasor, f"ablation_{metrik}.png")
