# Görev: "İl Bazında Kredi Riski Erken Uyarı Sistemi" için veri ve fizibilite denetimi

## Rolün

Türkiye finans verisi ve zaman serisi/panel ML konusunda deneyimli bir veri mühendisi ve ML araştırmacısısın. Bu repoda çalışıyorsun. Amacın yeni bir model kurmak değil: projenin **yapılabilir olup olmadığını kanıtla ölçmek**, eksik veri kaynaklarını (özellikle TÜİK) test etmek ve ekibe net bir **devam / değiştir / bırak** kararı için gereken bulguları üretmek.

Raporu Türkçe yaz. Teknik terimler İngilizce kalabilir. Sade, kısa, rakamlı yaz.

## Proje bağlamı

- GTU Bilgisayar Mühendisliği bitirme projesi. Ekip 3 kişi, süre Kasım 2026 – Haziran 2027.
- Ekip finans uzmanı değil. Python, React, Express.js ve PostgreSQL biliyor.
- **Hedef:** 81 ilin her biri için "önümüzdeki 4 çeyrekte takip oranı (NPL) belirgin artacak mı?" sorusunu tahmin etmek.
  - Takip oranı = Takipteki Alacaklar / Toplam Nakdi Krediler × 100.
  - İlk etiket önerisi: NPL(t+4) − NPL(t) ≥ 0,5 puan → 1.
- **Planlanan modeller:** Kural baseline, lojistik regresyon, LightGBM, sonra GRU/TFT ve SHAP.
- **Planlanan doğrulama:** Expanding-window zaman doğrulaması, eğitim ile test arasında 4 çeyreklik boşluk, rastgele k-fold yok.

## Kesin kurallar

1. **Sentetik veri yok.** Simülasyonla, üretici modelle ya da dil modeliyle veri veya etiket üretme. Eksik veriyi uydurma; eksik olarak raporla.
2. **Uydurma yok.** Seri kodu, URL, sütun adı ya da rakam tahmin ediyorsan bunu açıkça yaz. Doğrulayamadığını "doğrulanamadı" diye işaretle.
3. **Ham veriyi değiştirme.** `data/raw/` salt okunur. Yeni çıktılar `data/interim/`, `data/raw/<kaynak>_<YYYY-MM-DD>/` (yeni indirmeler) ve `reports/` altına gider.
4. **Gizli bilgi yok.** EVDS anahtarı yalnızca `EVDS_API_KEY` ortam değişkeninden okunur. Anahtarı koda, loga ya da rapora yazma.
5. **Ortam:** Her şeyi proje kökündeki `.venv` içinde çalıştır (`source .venv/bin/activate`, Python 3.15). Yeni paket gerekiyorsa venv'e kur ve `requirements.txt`'e ekle. Bir paket Python 3.15'te kurulmazsa durumu raporla ve `python3.12 -m venv .venv312` ile alternatif ortam öner. Sistem Python'una dokunma.
6. **Ağ isteklerinde nazik ol.** Zaman aşımı koy (bağlantı ≤ 20 s), sınırlı sayıda yeniden dene, istekler arasında bekle. Hiçbir siteyi yoğun biçimde tarama.
7. **Silme yok.** Var olan dosyaları silme ya da yeniden adlandırma; yalnızca öner.

## Repo'nun şu anki durumu (1 Kasım 2026)

```
grad/
├── .venv/                 # Python 3.15; pandas 3.1, numpy 2.5, requests, httpx, pybrsa 0.1.7, pytuik 0.1.0, sdmx1, openpyxl, lxml
├── finturk_indir.py       # BDDK FinTürk'ü pybrsa ile indirir (7 tablo, 81 il, 2010-03 → 2026-06, grup 10001)
├── evds.py                # EVDS makro indirici (docstring'de adı hâlâ evds_indir.py)
├── evds_test.py           # EVDS bağlantı testi
├── tuik_test.py           # pytuik ile TÜİK CİP katalog testi (henüz hiç çalışmadı)
└── data/raw/
    ├── finturk_2026-10-30/
    │   ├── tablo_1_krediler.csv              # 5.346 satır
    │   ├── tablo_2_mevduat.csv               # 5.346
    │   ├── tablo_3_bireysel_bankacilik.csv   # 5.346
    │   ├── tablo_4_secilmis_sektorel_krediler.csv
    │   ├── tablo_5_oranlar.csv               # 5.346
    │   ├── tablo_6_subeler_ve_nufus.csv      # 5.346
    │   └── tablo_7_altin.csv                 # 3.564 (2015-09'dan başlıyor, beklenen)
    └── evds_2026-10-30/
        ├── makro_aylik.csv
        └── makro_ceyreklik.csv               # 68 çeyrek; period sütunu FinTürk ile aynı biçimde (YYYY-MM)
```

Repoda henüz git, `.gitignore`, `requirements.txt` ve `README` yok.

### Bilinen gerçekler (yeniden doğrula, ama bunlardan yola çık)

- FinTürk CSV'lerinin ortak anahtar sütunları: `plaka` (1–81), `period` (`2010-03` … `2026-06`), `il_adi`, `grup_kod`, `Yıl`, `Ay`, `table_no`.
- `tablo_1`: `Toplam Nakdi Krediler`, `Nakdi Krediler`, `Takipteki Alacaklar`, `Gayrinakdi Krediler` (Bin TL). Toplam = Nakdi + Takipteki.
- `tablo_5`: Hazır `Takipteki Alacaklar Toplam Nakdi Kredi Oranı` var ve `tablo_1`'den hesaplanan oranla birebir aynı (fark < 1e-4). Ayrıca kredi/mevduat oranları ve 13 sektörel "Performans Oranı" var. `Denizcilik …` sütununda 2.065 boş değer; `Enerji`, `Finansal Kuruluşlar` ve `Metal` sütunlarında az sayıda boş değer var.
- `tablo_3`: Taşıt, konut, KMH, diğer tüketici kredisi, bireysel kredi kartı ve bunların takipteki tutarları.
- `tablo_6`: Şube sayısı, şubeye düşen nüfus, kişi başı kredi/takipteki/mevduat (TL).
- EVDS çeyreklik:
  - `tufe` (TP.FG.J0, 2003=100) **2026-01'de bitiyor**, çünkü TÜFE'nin baz yılı 2026'da değişti.
  - `fonlama_faizi` 2011'den başlıyor.
  - `eur_try`, `fonlama_faizi`, `ihtiyac_faizi`, `konut_faizi`, `tuketici_faizi` seri kodları resmi metaveriyle doğrulanmadı.
- **TÜİK erişimi:** 31 Ekim 2026'da `www.tuik.gov.tr`, `data.tuik.gov.tr`, `veriportali.tuik.gov.tr` ve `cip.tuik.gov.tr` hem ev ağından hem mobil ağdan TCP bağlantı aşamasında zaman aşımına düştü; Google normal açıldı. pytuik'e göre TÜİK SDMX servisi Ağustos 2026'dan beri anonim isteklere 401 veriyor; CİP etkilenmiyor.
- **Ön analiz bulgusu (kritik):** 0,5 puan eşiğiyle pozitif oran tüm veride %23,6 (1.263 / 5.022). Ama oran yıla göre çok dalgalanıyor: 2018'de %81, 2024'te %79, 2010/2022'de %0, 2020'de %3. Yani etiket büyük ölçüde **ülke geneli kredi döngüsünü** ölçüyor, ile özgü riski değil. Zamana göre bölünmüş bir testte bazı test yılları neredeyse tamamen 0 ya da 1 olabilir. Bu, fizibilitenin bir numaralı sorusu.

## Yapılacaklar

Her aşamayı sırayla yap. Her aşamanın sonunda kısa bir ara özet yaz. Bir aşama dış bir nedenle tamamlanamazsa (ağ, erişim), nedenini kanıtıyla kaydet ve sonraki aşamaya geç.

### Aşama 0: Repo hijyeni (kısa)

1. `requirements.txt` oluştur (`pip freeze`, venv içinden).
2. `.gitignore` oluştur: `.venv/`, `.venv*/`, `data/`, `__pycache__/`, `.env`, `*.ipynb_checkpoints`.
3. `evds.py` docstring'indeki dosya adını düzelt; başka davranış değiştirme.
4. `git init` yapma. Yalnızca önerini rapora yaz.

### Aşama 1: TÜİK erişim teşhisi ve veri testi

**Amaç:** TÜİK'e erişilebiliyor mu, erişilemiyorsa neden, ve projeye gereken il göstergeleri hangi yolla alınabilir?

1. **Ağ teşhisi:** Aşağıdaki adreslerin her biri için DNS çözümleme, TCP 443 bağlantısı, TLS el sıkışması ve HTTP durum kodunu ayrı ayrı ölç.
   - Adresler: `cip.tuik.gov.tr`, `data.tuik.gov.tr`, `veriportali.tuik.gov.tr`, `nsiws.tuik.gov.tr`, `www.tuik.gov.tr`.
   - Ölçüm araçları: `dig`/`nslookup`, `curl -v --connect-timeout 15`, `curl -4` ve `curl -6`, `openssl s_client -connect host:443 -servername host`.
   - Karşılaştırma için bir kontrol adresi kullan (`evds3.tcmb.gov.tr`, `www.bddk.org.tr`).
   - Sonucu tablo olarak raporla: adres, çözülen IP, hangi aşamada düştü, süre.
2. **Erişim varsa:** `tuik_test.py`'yi çalıştır ve çıktısını kaydet: `data/raw/tuik_<tarih>/katalog.csv`. Ardından `pytuik.geo_variables()` kataloğunda projeye aday göstergeleri bul. Her biri için şunları raporla: gösterge kodu, adı, düzey (il / İBBS-2), dönem aralığı, sıklık, eksik iller.
   - Aday göstergeler: işsizlik oranı, istihdam, konut satışları, yapı ruhsatı, girişim kuruluş/kapanış, il GSYH, kişi başı GSYH, nüfus, göç, sosyoekonomik skor, ihracat.
   - En fazla 5 gösterge için il düzeyinde veriyi indir ve FinTürk `plaka` ile eşleştir. Eşleşmeyen il adı veya kod kalmamalı.
3. **Erişim yoksa:** Durumu kanıtıyla yaz, sonra alternatifleri değerlendir. Hangisinin uygun olduğunu sen seçme; seçenekleri rapora koy.
   - (a) Erişim düzelince çalıştırılmak üzere hazır, zaman aşımlı ve tekrar denemeli bir `tuik_indir.py` yaz.
   - (b) TÜİK verisinin ikincil, açık ve güvenilir bir kopyası var mı? Örneğin EVDS'de TÜİK kaynaklı il serileri, ya da Kalkınma Ajansları ve SBB yayınları. Yalnızca gerçekten açıp doğruladığın kaynakları yaz.
   - (c) TÜİK'siz model: TÜİK yokken projenin ne kaybettiğini Aşama 4'teki ablation ile ölç.
4. TÜİK göstergelerinin çoğu yıllık. Her gösterge için **yayım gecikmesini** not et (yıl sonundan kaç ay sonra yayımlanıyor). Modelde ancak yayım tarihinden sonraki çeyreklerde kullanılabilir. Yayım tarihini doğrulayamazsan muhafazakâr bir gecikme öner ve bunu varsayım diye işaretle.

### Aşama 2: Diğer kaynakların doğrulanması

1. **EVDS seri kodları:** EVDS'nin seri/metaveri uçlarından doğrulanmamış 5 kodun resmi adını, birimini, sıklığını ve başlangıç tarihini çek. Yanlış seri varsa doğrusunu öner.
2. **TÜFE zincirleme:**
   - Yeni bazlı TÜFE serisinin EVDS kodunu bul ve doğrula.
   - Çakışan aylar üzerinden eski seriyle zincirleyerek 2010-01'den bugüne tek bir endeks üret: `data/interim/tufe_zincir.csv`.
   - Çakışma yoksa bunu açıkça yaz ve yöntemi ayrıca öner. Uydurma birleştirme yapma.
3. **FinTürk kalite kontrolleri** (bulguları tablo olarak raporla):
   - Her tablo için (plaka, period) anahtarının benzersizliği; 81 × 66 = 5.346 tam mı?
   - İl adlarının dönemler arasında tutarlılığı ve `plaka` eşlemesi.
   - Muhasebe tutarlılığı: Toplam = Nakdi + Takipteki; oranlar 0–100 aralığında mı?
   - Uç değerler ve ani sıçramalar: il bazında çeyreklik değişimde üst %0,5 dilim. Tanım değişikliği şüphesi olan dönemleri işaretle.
   - "YURT DIŞI" gibi il olmayan kayıtlar var mı?
   - Boş değerlerin dağılımı ve sektörel performans oranlarındaki boşlukların nedeni (kredi hacmi sıfır mı?).
4. **Revizyon kontrolü:** `pybrsa.fetch_finturk` ile 2–3 eski dönemi (örn. 2015-12, 2019-12, 2023-12) yeniden çek ve 30 Ekim indirmesiyle karşılaştır. Fark varsa revizyon var demektir; vintage stratejisinin önemini raporla. Yeni indirmeyi `data/raw/finturk_<bugün>_revizyon_kontrol/` altına koy.

### Aşama 3: Hedef değişken ve etiket fizibilitesi (en kritik aşama)

1. Analiz veri setini kur: `data/interim/panel.parquet` (il × çeyrek). Tüm FinTürk tablolarını ve EVDS çeyreklik verisini `plaka` ve `period` üzerinden birleştir. TL tutarlarını zincirlenmiş TÜFE ile reelleştir.
2. **Etiket alternatiflerini karşılaştır.** Her biri için şunları raporla: pozitif oranı (toplam ve yıllara göre), il bazında pozitif sayısı, yıl × il ısı haritası.
   - E1 (mutlak): ΔNPL₄ ≥ 0,25 / 0,5 / 1,0 puan.
   - E2 (göreli, ülkeden ayrışma): il ΔNPL₄ − Türkiye ΔNPL₄ ≥ eşik. Türkiye NPL'si kredi ağırlıklı toplamdan hesaplanacak.
   - E3 (sıralama): Her çeyrekte ΔNPL₄'e göre en kötü %20'lik dilimdeki iller.
   - E4 (regresyon): ΔNPL₄ ve ilin Türkiye'den sapması, sürekli hedef olarak.
   - İsteğe bağlı E5: takipteki tutarın 4 çeyreklik reel log-değişimi. Paydadaki kredi büyümesi etkisini ayırmak için.
3. **Sinyal-gürültü kontrolü:**
   - ΔNPL₄ varyansının ne kadarı yıl (çeyrek) sabit etkileriyle, ne kadarı il sabit etkileriyle açıklanıyor? Basit iki yönlü varyans ayrıştırması yeterli.
   - Yıl etkisi baskınsa, il düzeyinde öğrenilecek sinyalin ne kadar kaldığını açıkça yaz.
4. **Payda etkisi:** Hızlı kredi büyümesinin NPL oranını yapay olarak düşürdüğü il-çeyrekleri say. Örnek koşul: takipteki tutar artarken oran düşüyor.
5. **Önerini yaz:** Hangi etiket tanımı hem anlamlı hem öğrenilebilir? Gerekçesi ne?

### Aşama 4: Hızlı fizibilite deneyi (baseline düzeyi; derin model yok)

1. Seçtiğin iki etiket tanımıyla aynı deneyleri yap: ana öneri ve mutlak E1(0,5). Modeller:
   - B0: çoğunluk sınıfı
   - B1: "son 4 çeyrekte NPL arttıysa 1" kuralı
   - B2: lojistik regresyon
   - B3: LightGBM (makul varsayılanlar, küçük bir hiperparametre araması)
2. Özellikler, yalnızca t anında bilinen bilgiyle:
   - NPL gecikmeleri (1, 2, 4, 8 çeyrek) ve değişimleri
   - Kredi ve mevduat reel büyümesi
   - Kredi/mevduat oranı
   - Bireysel kredi türlerinin payı ve kendi takip oranları
   - Sektörel kredi payları
   - Kişi başı göstergeler
   - EVDS makro: yıllık TÜFE, USD/TL yıllık değişimi, faizler
   - Kontrollü bir deneyde ayrıca: komşu illerin ortalama NPL değişimi. Bunun için 81 ilin kara komşuluk tablosunu `data/interim/il_komsuluk.csv` olarak oluştur ve kaynağını yaz.
3. Doğrulama:
   - Expanding-window: örneğin 2010–2015 ile eğit, 2016'yı test et; ardından 2010–2016 ile eğit, 2017'yi test et; böyle devam et.
   - Eğitim ve test arasında 4 çeyreklik boşluk bırak (etiket sızıntısı olmasın).
   - Etiketi hesaplanamayan son 4 çeyreği dışarıda tut.
4. Metrikler:
   - PR-AUC, ROC-AUC, Brier, Precision@10 (her test çeyreğinde en riskli 10 il)
   - E4 için MAE ve Spearman
   - Tüm metrikleri hem test yılı bazında hem toplamda raporla. Tek sınıflı test yıllarını ayrıca işaretle.
5. Ablation:
   - (i) yalnızca FinTürk
   - (ii) FinTürk + EVDS
   - (iii) + komşu il
   - (iv) + TÜİK (eriştiysen)
   - Her eklemenin katkısını rakamla göster.
6. **Sızıntı denetimi:** En önemli 15 özelliği listele (LightGBM gain ve SHAP özetiyle). Her birinin tahmin anında gerçekten bilinip bilinmediğini tek tek kontrol et.
7. Kod `src/` altında küçük, okunur modüller olsun: `src/data.py`, `src/labels.py`, `src/features.py`, `src/evaluate.py`, ve tek bir çalıştırıcı `run_feasibility.py`. Rastgelelik için sabit tohum kullan.

### Aşama 5: Fizibilite kararı

Aşağıdaki ölçütlere göre her soruya **Evet / Kısmen / Hayır** ver, gerekçesini rakamla yaz:

| # | Soru | Geçme ölçütü (öneri; gerekirse gerekçeli değiştir) |
|---|---|---|
| 1 | Ana veri (FinTürk + EVDS) eksiksiz ve tutarlı mı? | 81 × 66 tam; kritik kalite sorunu yok ya da çözümü belli |
| 2 | Anlamlı ve dengeli bir etiket tanımı var mı? | Pozitif oranı %10–40; test yıllarının çoğunda iki sınıf da mevcut |
| 3 | Model basit kuralları geçiyor mu? | LightGBM PR-AUC'si B1 kuralından en az %10 göreli daha iyi; test yıllarının çoğunda üstün |
| 4 | İl düzeyinde sinyal var mı? | Göreli etiket (E2/E3) ile de baseline'ı geçiyor |
| 5 | TÜİK projeye gerekli mi? | Ablation'a göre katkısı; erişim yoksa proje TÜİK'siz yürür mü |
| 6 | Derin model (GRU/TFT) için veri yeterli mi? | Gözlem sayısı ve LightGBM'e göre beklenen kazanç hakkında gerekçeli görüş |
| 7 | 7 ayda bitirilebilir mi? | Kalan iş kalemleri ve riskler |

Sonunda tek bir karar ver: **DEVAM** (plan aynen), **DEĞİŞTİR** (ne değişmeli: etiket, kapsam, ek veri, Fikir 7 olan GNN kredi büyümesi görevinin eklenmesi gibi) ya da **BIRAK**. En fazla 5 maddelik gerekçe yaz.

## Teslim edilecekler

1. `reports/fizibilite_raporu.md`. Bölümleri:
   1. Yönetici özeti: 10 satırı geçmesin, karar ve en önemli 3 rakam.
   2. TÜİK erişim teşhisi ve veri durumu.
   3. Diğer kaynakların doğrulanması.
   4. Veri kalite kontrolleri.
   5. Etiket analizi: tablolar ve şekiller.
   6. Fizibilite deneyi sonuçları: metrik tabloları ve ablation.
   7. Sızıntı denetimi.
   8. Karar tablosu.
   9. Riskler ve önerilen sonraki adımlar: öncelik sırasıyla, her biri tahmini iş günü ile.
   10. Açık sorular: ekonomi hocasına ve danışmana.
   11. Doğrulanamayanlar listesi.
   12. Kaynaklar: açtığın her URL.
2. `reports/figures/`: Etiket ısı haritaları, yıllara göre pozitif oranı, NPL dağılımları, model metrikleri. PNG, okunur eksen etiketleriyle.
3. `src/` modülleri, `run_feasibility.py`, `tuik_indir.py`, güncel `requirements.txt` ve `.gitignore`.
4. `data/interim/` çıktıları: `panel.parquet`, `tufe_zincir.csv`, `il_komsuluk.csv`, ve TÜİK verisi indirildiyse o dosyalar.
5. `reports/calistirma_notlari.md`: Hangi komutları hangi sırayla çalıştırdığın, süreleri, karşılaştığın hatalar ve nasıl çözdüğün. Başka bir ekip üyesi her şeyi tek komutla yeniden üretebilmeli: `python run_feasibility.py`.

## Çalışma biçimi

- Her aşamaya başlarken kısa bir plan yaz. Bitince ne bulduğunu iki-üç cümleyle özetle.
- Bir varsayım yaptığında kodda yorum olarak, raporda "Varsayım" etiketiyle yaz.
- Bir şey beklenmedik çıkarsa (sütun yok, satır sayısı tutmuyor, metrik "fazla iyi") dur, nedenini araştır, sonra devam et. AUC > 0,9 gibi sonuçları sızıntı şüphesiyle ele al.
- Uzun indirmeleri ve deneyleri önce küçük bir alt kümede (2 il, 4 dönem) dene.
- İşin sonunda raporu baştan sona bir kez daha oku. Her rakamın bir çıktıdan geldiğini ve her URL'nin gerçekten açıldığını kontrol et.
