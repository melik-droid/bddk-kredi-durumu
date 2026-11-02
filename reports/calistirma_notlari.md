# Çalıştırma notları (1 Kasım 2026)

Tüm komutlar proje kökünde, `source .venv/bin/activate` sonrası çalıştırıldı (Python 3.15.2).

## Tek komutla yeniden üretme

```bash
source .venv/bin/activate
pip install -r requirements.txt        # macOS'ta LightGBM için ayrıca: brew install libomp
python run_feasibility.py              # yaklaşık 5-6 dakika
```

`run_feasibility.py` yalnızca `data/raw/` altındaki mevcut indirmeleri okur, ağa çıkmaz. Ürettikleri:
`data/interim/{panel.parquet, tufe_zincir.csv, il_komsuluk.csv}`, `reports/tablolar/*.csv`,
`reports/tablolar/ozet.json`, `reports/figures/*.png`.

Ham veriyi yeniden indirmek isterseniz (ağ gerekir, sırayla):

| Komut | Ne yapar | Süre | Not |
|---|---|---|---|
| `python finturk_indir.py` | BDDK FinTürk 7 tablo | ~10 dk | Var olan script, bu çalışmada yeniden çalıştırılmadı |
| `python evds.py` | EVDS makro | ~1 dk | `EVDS_API_KEY` gerekir. Var olan script, yeniden çalıştırılmadı |
| `python tuik_indir.py` | TÜİK CİP katalog + 11 aday gösterge özeti + 5 göstergenin ham verisi | ~45 s | Anahtar gerekmez |
| `export EVDS_API_KEY=$(tr -d ' \n\r' < ~/.evds_key); python evds_dogrula.py` | EVDS seri metaverisi, yeni bazlı TÜFE | ~2,5 dk | Anahtar dosyası repo dışında |

TÜFE Excel tabloları ve il sınırları `tuik_indir.py` içinde değil; bu çalışmada tek seferlik
komutlarla indirildi (aşağıda). `tuik_indir.py`'ye eklenmesi önerilir (yarım gün).

## Bu çalışmada sırayla yapılanlar

1. **Aşama 0.** `pip freeze > requirements.txt`; `.gitignore` yazıldı; `evds.py` docstring'inde
   `evds_indir.py` → `evds.py` düzeltildi. Başka davranış değişmedi.
2. **Ağ teşhisi.** `dig`, `curl -4/-6 --connect-timeout 15`, `openssl s_client` (5 TÜİK + 2 kontrol adresi).
   Ham çıktı: `reports/_ag_teshis_raw.txt`. Hepsi erişilebilir çıktı (31 Ekim'deki sorun yok).
3. **TÜİK CİP.** `tuik_test.py` çalıştırılmadı, çünkü çıktısını `data/raw/` köküne yazıyor (kural 3).
   Aynı işi yapan `tuik_indir.py` yazıldı ve çalıştırıldı (log: `reports/_tuik_indir_log.txt`).
4. **TÜFE tabloları.** `pytuik.TuikClient.get_tables(6)` → "Tüketici fiyat endeksi ve değişim oranları"
   iki istab tablosu `get_bytes` ile indirildi: `data/raw/tuik_2026-11-01/tufe_tablo_41.xls` (2003=100),
   `tufe_tablo_45.xls` (2025=100, 2005'e geriye uzatılmış). URL'ler raporun Kaynaklar bölümünde.
5. **İl sınırları ve İBBS eşlemesi.** `https://cip.tuik.gov.tr/assets/geometri/nuts3.json` →
   `il_sinirlari_duzey3.geojson`; `geo_map(3, geometry=False)` → `il_ibbs_eslesme.csv`.
6. **FinTürk revizyon kontrolü.** `pybrsa.fetch_finturk` ile tablo 1, 3, 5 için 2015-12, 2019-12, 2023-12,
   2026-06 yeniden çekildi → `data/raw/finturk_2026-11-01_revizyon_kontrol/`. (12 istek, 2 s bekleme.)
7. **EVDS.** Anahtar ortamda yoktu. Kullanıcı anahtarı `~/.evds_key` dosyasına koydu; komutta
   `export EVDS_API_KEY=$(...)` ile ortam değişkenine aktarıldı. Kod anahtarı yalnızca
   `os.environ` üzerinden okur; anahtar hiçbir dosyaya, loga ya da rapora yazılmadı.
8. **Paketler.** `pip install xlrd shapely scikit-learn lightgbm matplotlib pyarrow shap`; hepsi
   Python 3.15'te kuruldu. `.venv312` gerekmedi.
9. `python run_feasibility.py` (log: `reports/_run_log.txt`).

## Karşılaşılan hatalar ve çözümler

| Hata | Neden | Çözüm |
|---|---|---|
| İşsizlik oranı il düzeyinde 81 ilin 74'ünde NaN | pytuik 0.1.0 `geo_data` Türkçe ondalık virgülü (`"7,5"`) `pd.to_numeric` ile NaN yapıyor | `tuik_indir.py` `GetMapData`'yı pytuik istemcisiyle doğrudan çağırıp virgülü kendisi çeviriyor |
| CİP göstergeleri yalnızca son 5 yıl | Katalogdaki `kayitSayisi=5` | İstekte `kayitSayisi` yıllık 40, aylık 400 verildi; 2000'den beri seriler geldi |
| Aylık otomobil serisinde `"2025-0"` gibi tarihler | CİP aylık serilerde yıl değerini "ay 0" olarak da veriyor (değer = Aralık) | `data.tuik_ceyrek` bu satırları atıyor |
| SES skoru (ses123) boş | CİP il ve ilçe düzeyinde veri döndürmedi | Eksik olarak raporlandı |
| TÜFE tablo 45 ilk denemede HTML döndü | veriportali kısa aralıklı ikinci indirmeye "5 saniye bekleyin" sayfası veriyor | 12 s bekleyip yeniden indirildi |
| `import lightgbm` → `Library not loaded: @rpath/libomp.dylib` | macOS'ta LightGBM OpenMP'yi sistemden ister | `brew install libomp` (Homebrew; Python'a dokunmaz) |
| EVDS anahtarsız istek HTTP 403 | Beklenen | Anahtar ortam değişkeniyle verildi |
| `run_feasibility.py` ilk çalıştırmada `TypeError: 'DataFrame' object is not callable` | Adım dekoratörü fonksiyonu hemen çalıştırıyordu | Dekoratör düzeltildi |
| `KeyError: t6_kisi_basi_toplam_mevduati` | Sütun adı `t6_kisi_basi_toplam_mevduat` | Düzeltildi |

## Dosya işlemleri

- Silinen tek dosya: bu oturumda kendi oluşturduğum `data/raw/tuik_2026-11-01/ISKYT-GK378267475-O12101_duzey3.csv`
  (seçim listesi değişince). Önceden var olan hiçbir dosya silinmedi ya da yeniden adlandırılmadı.
- `data/raw/tuik_2026-11-01/katalog.csv` aynı gün içinde `tuik_indir.py` tarafından (TR+EN adlarla) üzerine yazıldı.
- Değiştirilen var olan dosya: yalnızca `evds.py` (docstring, 1 satır).
