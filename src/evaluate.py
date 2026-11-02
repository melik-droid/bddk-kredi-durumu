"""Expanding-window zaman doğrulaması, baseline'lar, LR, LightGBM ve metrikler."""
import itertools
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

TOHUM = 42
BOSLUK = 4          # eğitim ile test arasında boşluk (çeyrek)
TEST_YILLARI = list(range(2016, 2026))  # 2025 yalnızca Q1-Q2 (etiketi olan son çeyrekler)
LGB_IZGARA = {"num_leaves": [7, 15], "min_child_samples": [20, 60], "n_estimators": [150, 400]}
LGB_SABIT = dict(learning_rate=0.03, subsample=0.8, subsample_freq=1, colsample_bytree=0.7,
                 reg_lambda=1.0, random_state=TOHUM, n_jobs=4, verbose=-1)


def katlar(donem):
    """Her test yılı için (eğitim maskesi, test maskesi). Eğitim: t <= test başlangıcı - (BOSLUK+1).

    Örnek: test 2016 -> eğitim 2010Q1..2014Q4 (son eğitim etiketi 2015Q4'te gerçekleşmiş olur).
    """
    for y in TEST_YILLARI:
        bas = pd.Period(f"{y}Q1", "Q")
        egitim = donem <= bas - (BOSLUK + 1)
        test = (donem >= bas) & (donem <= pd.Period(f"{y}Q4", "Q"))
        yield y, egitim, test


# ----------------------------------------------------------------------- modeller
def lr_model():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(C=0.1, max_iter=2000))


def lgb_ara(X, y, donem, gorev="ikili"):
    """Eğitim içinde son 4 çeyreği doğrulama (öncesinde 4 çeyrek boşluk) yaparak küçük ızgara araması."""
    son = donem.max()
    ic_dog = donem > son - 4
    ic_eg = donem <= son - 4 - BOSLUK
    en_iyi, en_iyi_skor = None, -np.inf
    if ic_eg.sum() < 200 or (gorev == "ikili" and y[ic_dog].nunique() < 2):
        return dict(num_leaves=7, min_child_samples=60, n_estimators=150)
    for nl, mcs, ne in itertools.product(*LGB_IZGARA.values()):
        prm = dict(num_leaves=nl, min_child_samples=mcs, n_estimators=ne)
        if gorev == "ikili":
            m = lgb.LGBMClassifier(**prm, **LGB_SABIT).fit(X[ic_eg], y[ic_eg])
            skor = average_precision_score(y[ic_dog], m.predict_proba(X[ic_dog])[:, 1])
        else:
            m = lgb.LGBMRegressor(**prm, **LGB_SABIT).fit(X[ic_eg], y[ic_eg])
            skor = -mean_absolute_error(y[ic_dog], m.predict(X[ic_dog]))
        if skor > en_iyi_skor:
            en_iyi, en_iyi_skor = prm, skor
    return en_iyi


# ----------------------------------------------------------------------- metrikler
def precision_at_k(y, skor, donem, k=10):
    v = []
    for _, g in pd.DataFrame({"y": y, "s": skor, "d": donem}).groupby("d"):
        v.append(g.nlargest(k, "s")["y"].mean())
    return float(np.mean(v))


def ikili_metrik(y, skor, olasilik, donem):
    tek = y.nunique() < 2
    return {
        "n": len(y),
        "pozitif_oran": round(float(y.mean()), 3),
        "tek_sinif": tek,
        "PR_AUC": np.nan if tek else average_precision_score(y, skor),
        "ROC_AUC": np.nan if tek else roc_auc_score(y, skor),
        "Brier": brier_score_loss(y, olasilik) if olasilik is not None else np.nan,
        "P@10": precision_at_k(y, skor, donem),
    }


def surekli_metrik(y, tahmin, donem):
    rho_q = [spearmanr(g["y"], g["t"]).statistic
             for _, g in pd.DataFrame({"y": y, "t": tahmin, "d": donem}).groupby("d")]
    return {"n": len(y), "MAE": mean_absolute_error(y, tahmin),
            "Spearman_toplam": spearmanr(y, tahmin).statistic,
            "Spearman_ceyrek_ort": float(np.nanmean(rho_q))}


# ----------------------------------------------------------------------- deney
def ikili_deney(X, y, donem, b1_skor, etiket, ozellik_seti):
    """Bir ikili etiket ve özellik seti için tüm katları koşar. Satır başına tahminleri döndürür."""
    tahminler = []
    for yil, eg, te in katlar(donem):
        eg = eg & y.notna()
        te = te & y.notna()
        if te.sum() == 0:
            continue
        Xe, ye, Xt, yt = X[eg], y[eg].astype(int), X[te], y[te].astype(int)
        oncelik = float(ye.mean())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lr = lr_model().fit(Xe, ye)
            prm = lgb_ara(Xe, ye, donem[eg])
            gbm = lgb.LGBMClassifier(**prm, **LGB_SABIT).fit(Xe, ye)
        out = pd.DataFrame({
            "etiket": etiket, "set": ozellik_seti, "test_yili": yil, "donem": donem[te],
            "y": yt,
            "B0": oncelik,
            "B1": b1_skor[te].fillna(0).values,
            "B2_LR": lr.predict_proba(Xt)[:, 1],
            "B3_LGBM": gbm.predict_proba(Xt)[:, 1],
        }, index=Xt.index)
        out["lgb_parametre"] = str(prm)
        tahminler.append(out)
    return pd.concat(tahminler)


def ikili_ozet(tah):
    """Model x (test yılı + toplam) metrik tablosu. B1 Brier'ı kuralın 0/1 çıktısıyla."""
    satirlar = []
    for model in ["B0", "B1", "B2_LR", "B3_LGBM"]:
        for yil, g in list(tah.groupby("test_yili")) + [("TOPLAM", tah)]:
            if model == "B1":
                olas = (g["B1"] > 0).astype(float)
            elif model == "B0":
                olas = g["B0"]
            else:
                olas = g[model]
            skor = g[model] + (np.random.default_rng(TOHUM).normal(0, 1e-9, len(g)) if model == "B0" else 0)
            m = ikili_metrik(g["y"], skor, olas, g["donem"])
            m.update(model=model, test_yili=yil)
            satirlar.append(m)
    return pd.DataFrame(satirlar)


def surekli_deney(X, y, donem, b1, hedef, ozellik_seti):
    tahminler = []
    for yil, eg, te in katlar(donem):
        eg = eg & y.notna()
        te = te & y.notna()
        if te.sum() == 0:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rd = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0)).fit(X[eg], y[eg])
            prm = lgb_ara(X[eg], y[eg], donem[eg], gorev="surekli")
            gbm = lgb.LGBMRegressor(**prm, **LGB_SABIT).fit(X[eg], y[eg])
        tahminler.append(pd.DataFrame({
            "hedef": hedef, "set": ozellik_seti, "test_yili": yil, "donem": donem[te], "y": y[te],
            "B0_egitim_ort": float(y[eg].mean()),
            "B1_son4": b1[te].fillna(0).values,
            "B2_Ridge": rd.predict(X[te]),
            "B3_LGBM": gbm.predict(X[te]),
        }, index=X[te].index))
    return pd.concat(tahminler)


def surekli_ozet(tah):
    satirlar = []
    for model in ["B0_egitim_ort", "B1_son4", "B2_Ridge", "B3_LGBM"]:
        for yil, g in list(tah.groupby("test_yili")) + [("TOPLAM", tah)]:
            t = g[model] + (np.random.default_rng(TOHUM).normal(0, 1e-9, len(g)) if model.startswith("B0") else 0)
            m = surekli_metrik(g["y"], t, g["donem"])
            m.update(model=model, test_yili=yil)
            satirlar.append(m)
    return pd.DataFrame(satirlar)
