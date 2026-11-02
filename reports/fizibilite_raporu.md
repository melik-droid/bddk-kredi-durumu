# İl Bazında Kredi Riski Erken Uyarı Sistemi: Veri ve Fizibilite Denetimi

Tarih: 1 Kasım 2026 · Kapsam: 81 il × 66 çeyrek (2010Q1–2026Q2) · Yeniden üretim: `python run_feasibility.py`

Tablolardaki her rakam `reports/tablolar/` altındaki bir CSV'den ya da `reports/tablolar/ozet.json`'dan gelir.
Her bölümde kaynağı yazıyor.

---

## 1. Yönetici özeti

**Karar: DEĞİŞTİR.** Veri tarafı sağlam. Asıl sorun hedef. Planlanan mutlak etiket öğrenilebilir değil.

- **%58.** ΔNPL₄ varyansının %58,4'ü yalnızca çeyrek (ülke döngüsü) etkisiyle açıklanıyor. İl sabit etkisinin payı %1,2. Mutlak etiket E1(0,5) aslında "Türkiye'de NPL artacak mı?" sorusunu ölçüyor (bkz. 5.3).
- **0,288 / 0,333.** E1(0,5) için tüm test yılları birlikte değerlendirildiğinde LightGBM'in PR-AUC'si 0,288. Basit "son 4 çeyrekte arttıysa" kuralı (B1) 0,333 alıyor, yani model kuralın gerisinde.
- **+%9.** Göreli etikette (E3, her çeyrekte en kötü %20) LightGBM PR-AUC'si 0,247, B1 0,226. Bu %9 göreli kazanç demek ve %10 eşiğinin altında. ROC-AUC 0,575. İl düzeyinde sinyal var ama zayıf. En güçlü sinyal sürekli göreli hedefte: çeyrek içi Spearman 0,32 (B1: 0,10).
- **TÜİK erişilebilir ve 5 gösterge indirildi**, ancak katkısı ölçülemeyecek kadar küçük. E3 için +0,011 PR-AUC, E1 için −0,016. TÜİK projede zorunlu değil.
- Önerilen değişiklik: hedefi **göreli sıralama** (E3 ya da sürekli göreli ΔNPL) olarak tanımla, ana metrik P@10 ve Spearman olsun. GRU/TFT'yi kapsamdan çıkar (en fazla deneysel ek olarak kalsın). Tek borçlu kaynaklı sıçramalar için temizleme kuralı ekle.

---

## 2. TÜİK erişim teşhisi ve veri durumu

### 2.1 Ağ teşhisi (1 Kasım 2026, 15:28–15:30 +03, ev ağı)

Ham çıktı: `reports/_ag_teshis_raw.txt`. Araçlar: `dig`, `curl -4/-6 --connect-timeout 15`, `openssl s_client`.

| Adres | Çözülen IP | DNS | TCP 443 | TLS | HTTP | Toplam (curl -4) |
|---|---|---|---|---|---|---|
| cip.tuik.gov.tr | 212.174.172.216 | ✓ | ✓ 0,22 s | ✓ TLS1.2, *.tuik.gov.tr (GeoTrust) | 200 | 0,82 s |
| data.tuik.gov.tr | 212.174.172.247 | ✓ | ✓ 0,26 s | ✓ | 302 → veriportali | 0,88 s |
| veriportali.tuik.gov.tr | 212.174.29.216 | ✓ | ✓ 0,56 s | ✓ TLS1.2 | 200 | 1,61 s |
| nsiws.tuik.gov.tr | 212.174.29.216 | ✓ | ✓ 0,18 s | ✓ TLS1.2 | 200 | 2,94 s |
| www.tuik.gov.tr | 212.174.172.222 | ✓ | ✓ 0,17 s | ✓ | 200 | 1,14 s |
| evds3.tcmb.gov.tr (kontrol) | 185.98.252.184 | ✓ | ✓ 0,19 s | ✓ | 200 | 0,69 s |
| www.bddk.org.tr (kontrol) | 212.175.177.81 | ✓ | ✓ 0,20 s | ✓ | 200 | 2,73 s |

- Hiçbir adres AAAA kaydı döndürmedi. `curl -6` sonuçları `::ffff:` biçimli IPv4 adresine gitti; bu yüzden IPv6 ayrıca test edilemedi.
- **Sonuç:** 31 Ekim'de görülen TCP zaman aşımı 1 Kasım'da yok. Neden (geçici kesinti mi, TÜİK tarafında filtre mi) **doğrulanamadı**.
- SDMX servisinin (nsiws) anonim isteklere 401 verdiği bilgisi ayrıca test edilmedi. CİP ve veriportali indirmeleri bu servise ihtiyaç duymadı.

### 2.2 CİP gösterge kataloğu

`data/raw/tuik_2026-11-01/katalog.csv`: 80 gösterge (TR ve EN adlarıyla). Aday göstergeler `aday_ozet.csv` dosyasında.

| Gösterge | CİP kodu | Düzey | Dönem | Sıklık | Eksik il | Önerilen yayım gecikmesi (Varsayım) |
|---|---|---|---|---|---|---|
| İşsizlik oranı | ISGD-GK18575-O18504 | il | 2022–2025 | yıllık | 0 | — |
| İşsizlik oranı | ISGD-GK18575-O18504 | İBBS-2 (26) | 2014–2025 | yıllık | 0 bölge | 4 ay |
| İstihdam oranı | ISGD-GK18575-O18506 | il / İBBS-2 | 2022–2025 / 2014–2025 | yıllık | 0 | 4 ay |
| Konut satışı (toplam) | INS-GK055-O006 | il | 2013–2025 | yıllık | 0 | 2 ay |
| Yapı ruhsatı, daire | INS-GK058-O006 | il | 2010–2025 | yıllık | 0 | 3 ay |
| Girişim sayısı | ISKYT-GK378267475-O12101 | il | 2009–2024 | yıllık | 0 | 12 ay |
| İl GSYH (bin TL) | UHS-GK097-O0011 | il | 2000–2024 | yıllık | 0 | 12 ay |
| Kişi başı GSYH (TL) | UHS-GK096-O0011 | il | 2000–2024 | yıllık | 0 | 12 ay |
| Nüfus | ADNKS-GK137473-O29001 | il | 2007–2025 | yıllık | 0 | 2 ay |
| Net göç hızı (‰) | ADNKS-GK140832-O29009 | il | 2008–2025 | yıllık | 0 | 3 ay (6 ay daha güvenli) |
| Sosyoekonomik skor | ses123 | il / ilçe | **veri gelmedi** | — | 81 | — |
| Otomobil sayısı | ULS-GK111403-O12001 | il | 1995-12 → 2026-09 | aylık | ilk yıllarda 21 il | 2 ay |
| İhracat (il) | — | — | **CİP kataloğunda yok** | — | — | — |

Yayım gecikmeleri TÜİK bülten takvimiyle tek tek **doğrulanmadı**. Yukarıdaki değerler muhafazakâr varsayımlardır ve `src/data.py` içindeki `TUIK_GOSTERGELER` sözlüğünde tanımlıdır. Bir değer, ancak ait olduğu yıl sonu ile gecikmenin toplamından sonraki çeyrekten itibaren modele girer.

### 2.3 İndirilen 5 gösterge ve plaka eşleşmesi

Dosyalar `data/raw/tuik_2026-11-01/` altında:

- `ISGD-GK18575-O18504_duzey2.csv` (işsizlik, İBBS-2)
- `INS-GK055-O006_duzey3.csv` (konut satışı)
- `UHS-GK096-O0011_duzey3.csv` (kişi başı GSYH)
- `ADNKS-GK140832-O29009_duzey3.csv` (net göç hızı)
- `ULS-GK111403-O12001_duzey3.csv` (otomobil, aylık)

Eşleşme şöyle yapıldı:

- **İl düzeyi:** `duzeyKodu` doğrudan plaka. 81/81 eşleşti, eşleşmeyen yok.
- **İBBS-2:** TÜİK'in kendi il→bölge tablosu kullanıldı (`il_ibbs_eslesme.csv`, kaynak CİP `nuts3.json` öznitelikleri). 81 il 26 bölgeye eşlendi.
- **İl adı farkı:** TÜİK iki ili farklı yazıyor: KAYSERI (FinTürk: KAYSERİ) ve NEVSEHİR (FinTürk: NEVŞEHİR). Eşleme plaka üzerinden yapıldığı için sorun çıkarmıyor (`kalite_il_adi_tuik.csv`).

**pytuik 0.1.0'da bulunan iki hata:**

1. Türkçe ondalık virgül (`"7,5"`) NaN'a dönüşüyor. Bu yüzden işsizlik oranı ilk denemede 81 ilin yalnızca 7–9'unda dolu geldi.
2. Katalogdaki `kayitSayisi=5` değeri yüzünden yalnızca son 5 yıl dönüyor.

`tuik_indir.py` ikisini de aşıyor. Ayrıca CİP aylık serilerde "YYYY-0" satırı yıllık değeri (Aralık değerinin aynısını) taşıyor; bu satır atılıyor.

### 2.4 Erişim kesilirse alternatifler (karar ekibin)

- **(a)** `tuik_indir.py` hazır: zaman aşımı 20 s, 2 yeniden deneme, istekler arasında 2 s bekleme. Erişim hatasında `hata.txt` yazar.
- **(b)** EVDS'de TÜİK kaynaklı il serisi **var** ve doğrulandı. "KONUT, İŞ YERİ VE İNŞAAT İSTATİSTİKLERİ (TÜİK)" kategorisinde `TP.AKONUTSAT{2,3,4}.(K)TR###` kodlarıyla 81 il + Türkiye için aylık konut ve iş yeri satışları bulunuyor (ipotekli, ilk el, ikinci el; 2013-01 → 2026-09; 664 seri, `seri_katalog.csv`). Bu seriler CİP'teki yıllık konut satışından daha güncel. İşgücü kategorisinde yalnızca Türkiye geneli var (16 seri), il ya da bölge yok. Kalkınma Ajansı ve SBB yayınları **açılmadı, doğrulanmadı**.
- **(c)** TÜİK'siz model: ablation sonuçları Bölüm 6.3'te. Kayıp önemsiz.

---

## 3. Diğer kaynakların doğrulanması

### 3.1 EVDS seri kodları

Kaynak: `evds_dogrula.py` → `data/raw/evds_2026-11-01/kod_dogrulama.csv`. Yöntem: categories → datagroups → serieList uçları. 10 kategoride 7.154 serinin metaverisi tarandı.

| Kod | Resmi ad | Sıklık | Başlangıç | Son | Veri grubu | Durum |
|---|---|---|---|---|---|---|
| TP.DK.USD.A.YTL | (USD) ABD Doları (Döviz Alış) | günlük | 1950-01-02 | 2026-11-02 | bie_dkdovytl | doğru |
| TP.DK.EUR.A.YTL | (EUR) Euro (Döviz Alış) | günlük | 1999-01-04 | 2026-11-02 | bie_dkdovytl | **doğrulandı** |
| TP.APIFON4 | TCMB Ağırlıklı Ortalama Fonlama Maliyeti | iş günü | 2011-01-03 | 2026-10-30 | bie_apifon | **doğrulandı** (EVDS varsayılan toplaması "last", evds.py ortalama alıyor; ikisi de savunulabilir) |
| TP.KTF10 | İhtiyaç Kredisi (TL, Akım, %) | haftalık | 2002-01-04 | 2026-10-16 | bie_kt100h | **doğrulandı** |
| TP.KTF12 | Konut Kredisi (TL, Akım, %) | haftalık | 2002-01-04 | 2026-10-16 | bie_kt100h | **doğrulandı** |
| TP.KTFTUK | Tüketici Kredisi (İhtiyaç+Taşıt+Konut) (TL, Akım, %) | haftalık | 2002-01-04 | 2026-10-16 | bie_kt100h | **doğrulandı** |
| TP.FG.J0 | GENEL (Tüketici) (Arşiv) | aylık | 2003-01 | **2026-01** | bie_tukfiy4 | arşivlenmiş seri |

- Birim: EVDS metaverisinde ayrı bir birim alanı yok. Birimler seri adlarından okundu (%, TL).
- Yanlış kod çıkmadı.
- Faiz serilerinin kaynağı "Mevduat, Kalkınma ve Yatırım Bankaları". Katılım bankaları kapsamda değil.

### 3.2 TÜFE zincirleme

**Yeni bazlı seri bulundu:** `TP.TUKFIY2025.GENEL` ("Genel Endeks", veri grubu bie_tukfiy2025, 2005-01 → 2026-09). Ayrıca `TP.GENENDEKS.T1` adlı seri 2003=100 bazını 2026-09'a kadar sürdürüyor. 31 Ekim'de görülen kesinti yalnızca arşivlenmiş `TP.FG.J0` kodundan kaynaklanıyordu.

`data/interim/tufe_zincir.csv` (2010-01 → 2026-09, 201 ay) şu bileşenlerden kuruldu:

- **Ana seri:** TÜİK veriportali "Tüketici fiyat endeksi ve değişim oranları [2025=100]" tablosu. TÜİK bu tabloyu 2005'e kadar geriye uzatılmış olarak yayımlıyor.
- **Doğrulama 1:** Eski 2003=100 seriyle 193 çakışan ay (2010-01 → 2026-01) var. Yeni/eski oranının değişim katsayısı **2,4·10⁻⁶**, yani oran sabit ve yeni seri eskinin sabit bir katı.
- **Doğrulama 2:** Eski seriyi 2025-12 oranıyla zincirleyip sonrasını yeni serinin aylık değişimleriyle uzatan bağımsız zincir kuruldu. Ana seriden en büyük farkı %0,0000088.
- **Doğrulama 3:** EVDS `TP.TUKFIY2025.GENEL` ile TÜİK tablosu arasındaki en büyük mutlak fark **0,0** (201 ay).

**Ham çeyreklik dosyada bulunan hata:** `makro_ceyreklik.csv` 2026Q1 TÜFE değerini Ocak ayından alıyor ("çeyreğin son mevcut ayı" mantığı yüzünden). Panelde çeyrek sonu ayı açıkça seçiliyor. 3 ayı tamamlanmamış 2026Q4 ise boş bırakılıyor.

**Öneri:** `evds.py` içinde `TP.FG.J0` kodunu `TP.TUKFIY2025.GENEL` ile değiştirin. Bu çalışmada `evds.py`'nin davranışı değiştirilmedi.

### 3.3 FinTürk'ün güncelliği

1 Kasım'da 2026-09 çeyreği yayımlanmış durumda (Ankara, tablo 1 için tek test isteği dolu döndü). Bu çeyrek panele **eklenmedi**. Eklenmesi bir etiketli çeyrek (2025Q3) daha kazandırır.

Yayım gecikmesi hakkındaki bulgu şu: 2026-06 verisi 30 Ekim'de mevcuttu, 2026-09 verisi 1 Kasım'da mevcut. Buna göre gecikme yaklaşık 1–2 ay. Kesin yayım tarihi **doğrulanamadı**.

---

## 4. Veri kalite kontrolleri

### 4.1 Anahtar ve kapsam (`kalite_anahtar.csv`)

| Tablo | Satır | İl | Dönem | Beklenen | Tekrarlanan (plaka, period) | Plaka başına tek il adı | İl olmayan kayıt |
|---|---|---|---|---|---|---|---|
| 1 krediler | 5.346 | 81 | 66 | 5.346 | 0 | evet | 0 |
| 2 mevduat | 5.346 | 81 | 66 | 5.346 | 0 | evet | 0 |
| 3 bireysel | 5.346 | 81 | 66 | 5.346 | 0 | evet | 0 |
| 4 sektörel | 5.346 | 81 | 66 | 5.346 | 0 | evet | 0 |
| 5 oranlar | 5.346 | 81 | 66 | 5.346 | 0 | evet | 0 |
| 6 şube/nüfus | 5.346 | 81 | 66 | 5.346 | 0 | evet | 0 |
| 7 altın | 3.564 | 81 | 44 | 3.564 | 0 | evet | 0 (2015-09'dan başlıyor) |

- Plaka → il eşlemesi resmi plaka listesiyle aynı (örn. 33 MERSİN, 80 OSMANİYE).
- "YURT DIŞI" kaydı yok, çünkü indirme yalnızca 1–81 plakalarını istedi. pybrsa'da 999 kodu yurt dışını temsil ediyor.
- Tüm tablolarda `grup_kod` = 10001 (sektör toplamı).

### 4.2 Muhasebe tutarlılığı (`kalite_muhasebe.csv`)

| Kontrol | Sonuç |
|---|---|
| Toplam = Nakdi + Takipteki, \|fark\| > 1 Bin TL olan satır | 0 |
| Hesaplanan NPL ile tablo_5 hazır oranı arasındaki en büyük fark | 0,0001 puan (yuvarlama) |
| Takip/performans oranları 0–100 dışında | 0 |
| Kredi/mevduat oranı > 100 (bilgi amaçlı, hata değil) | 4.310 satır |
| Bireysel kredi toplamı > toplam nakdi kredi | 0 |
| Negatif hücre / sıfır toplam kredi | 0 / 0 |

### 4.3 Boş değerler (`kalite_bos_deger.csv`)

| Sütun | Boş | Kredi + takipteki = 0 | Kredi > 0 | Etkilenen il |
|---|---|---|---|---|
| Denizcilik performans oranı | 2.065 | 2.065 | 0 | 55 |
| Enerji | 13 | 13 | 0 | 5 |
| Finansal kuruluşlar | 12 | 12 | 0 | 3 |
| Metal | 2 | 2 | 0 | 1 |

**Neden:** Boş oranların tamamında kredi hacmi sıfır. Bunlar gerçek eksik veri değil, 0/0 bölmesi.

### 4.4 Uç değerler ve sıçramalar

Kaynak: `kalite_sicrama_ozet.csv`, `kalite_sicrama_detay.csv`. Eşik: il bazında çeyreklik değişimin üst %0,5'i (seri başına 27 gözlem).

- **NPL sıçraması (> 1,65 puan):** Şüpheli olaylar tek il ve tek sektörde yoğunlaşıyor:
  - **Osmaniye 2024-09:** NPL 1,58 → **19,45** → 2,29. Metal sektörü takipteki alacağı tek çeyrekte 5,5 milyon → 8,0 milyar Bin TL'ye çıkıp bir sonraki çeyrekte geri düşüyor. Ya tek bir büyük borçlunun takibe girip hemen satılması/aktiften silinmesi ya da raporlama hatası. **Doğrulanamadı.**
  - **Amasya 2015-03:** 2,68 → 7,74 → 2,72. Aynı geri dönüş deseni.
  - **Karaman 2025-06:** 2,04 → 8,02, sonra kalıcı. Gıda sektörü takipteki alacağı 72 milyon → 1,95 milyar. Büyük olasılıkla tek bir büyük firma.
  - **Kütahya 2019-09:** 5,52 → 10,89, sonra kalıcı.
- **Kredi sıçraması:** 2010-09'da 13 il aynı anda +%30 ile +%137 arası artış gösteriyor (log-değişim 0,26–0,86; Siirt 0,86, Şırnak 0,69). Türkiye toplamında kredi o çeyrekte +%15,4. İl atama tanımında değişiklik **şüphesi** var. Öneri: 2010Q3'ü özelliklerde kullanırken dikkat edin ya da örneği 2011'den başlatın.
- **Mevduat 2021-12:** 10 ilde sıçrama var. Aynı çeyrekte kredi +%20,7. Bu kur şokuyla açıklanabilir (YP mevduatın TL karşılığı arttı); tanım değişikliği değil.
- **Sonuç:** Kritik bir kalite sorunu yok. Ancak küçük illerde NPL **tek borçluya duyarlı**. 1 çeyrek sonra geri dönen sıçramalar etiketi doğrudan bozuyor (t−4'te pozitif, t'de negatif etiket üretiyor). Temizleme kuralı gerekli (Bölüm 9).

### 4.5 Revizyon kontrolü (`kalite_revizyon.csv`)

Tablo 1, 3 ve 5 için 2015-12, 2019-12, 2023-12 ve 2026-06 dönemleri 1 Kasım'da yeniden indirildi (`data/raw/finturk_2026-11-01_revizyon_kontrol/`). Sonuç: **0 farklı hücre**, 12 karşılaştırmanın hepsinde.

Sınırlama: İki indirme arasında yalnızca 2 gün var. Bu sonuç geçmiş dönemlerin aylar içinde revize edilip edilmediğini göstermez. Vintage riski **doğrulanamadı**. Öneri: Her ay bir anlık görüntü alın (`data/raw/finturk_<tarih>/` zaten bu yapıda) ve 3 ay sonra karşılaştırın.

---

## 5. Etiket analizi

Etiketli gözlem sayısı 5.022 (2010Q1–2025Q2). Son 4 çeyrek (324 satır) etiketsiz.

### 5.1 Pozitif oranları (`etiket_ozet.csv`, `etiket_yillik.csv`)

| Etiket | Pozitif oranı | Yıllık oran min–maks | Oranı %10–40 arasında olan yıl (16 yılda) | Tek sınıfa yakın yıl (<%5 ya da >%95) | Hiç pozitifi olmayan il |
|---|---|---|---|---|---|
| E1 ≥0,25 | %34,8 | %0 – %92,9 | 7 | 3 | 0 |
| **E1 ≥0,5** | **%25,1** | **%0 – %81,5** | 7 | 4 | 0 |
| E1 ≥1,0 | %11,2 | %0 – %51,9 | 3 | 8 | 3 |
| E2 ≥0,25 | %29,7 | %9,0 – %55,9 | 11 | 0 | 1 |
| E2 ≥0,5 | %17,9 | %3,1 – %42,6 | 12 | 2 | 2 |
| E2 ≥1,0 | %6,4 | %0,3 – %16,0 | 2 | 5 | 18 |
| **E3 (en kötü %20)** | **%19,8** | **%19,8 – %19,8** | 16 | 0 | 0 |

- Ön analizdeki %23,6 (1.263/5.022) yerine **%25,1** çıktı. Pay aynı (1.263), oran farklı. Önceki hesap muhtemelen 5.346 satırı payda almıştı: 1.263/5.346 = %23,6. Doğru payda 5.022.
- E1(0,5) yıllara göre: 2018'de %81,5, 2024'te %79,3, 2010'da %0, 2022'de %0,3. Ön analizdeki bulgu doğrulandı.
- Şekiller:
  - `figures/pozitif_oran_yillik.png`
  - `figures/isi_haritasi_E1_0.5.png`: dikey şeritler, yani yıl etkisi baskın
  - `figures/isi_haritasi_E2_0.5.png`
  - `figures/isi_haritasi_E3.png`
  - `figures/npl_dagilim.png`
- E1(0,5) ile Türkiye ΔNPL₄ arasındaki çeyreklik korelasyon **0,79**.

### 5.2 Varyans ayrıştırması (`varyans_ayristirma.csv`, `figures/varyans_ayristirma.png`)

| Hedef | Çeyrek etkisi R² | İl etkisi R² | İki yönlü R² | İl × çeyrek kalanı |
|---|---|---|---|---|
| ΔNPL₄ | **0,584** | 0,012 | 0,596 | 0,404 |
| ΔNPL₄ − Türkiye ΔNPL₄ (göreli) | 0,148 | 0,024 | 0,173 | 0,827 |
| E5: takipteki reel log-değişim | 0,708 | 0,013 | 0,720 | 0,280 |
| E5 göreli | 0,246 | 0,032 | 0,278 | 0,722 |

Çeyrek etkisi eşit ağırlıklı il ortalamasıdır. Göreli hedefte kalan %14,8'lik çeyrek etkisi, kredi ağırlıklı Türkiye ortalamasıyla eşit ağırlıklı il ortalaması arasındaki farktan geliyor (İstanbul baskın).

**Yorum:**

- Mutlak hedefin %58'i ülke döngüsü. Döngü bilgisi illerde ortak olan makro özelliklerden gelmek zorunda. Oysa 16 yılda yalnızca 3–4 bağımsız döngü var (2015, 2018, 2024 artışları; 2020–2022 düşüşleri). 16 yıllık bir zaman serisinden bu kadar az döngüyle döngü tahmini öğrenilemez.
- İl düzeyinde öğrenilecek varyans payı %40 (il × çeyrek kalanı). Ne kadarının sinyal, ne kadarının tek borçlu gürültüsü olduğunu Bölüm 6 ölçüyor: sinyal küçük.

### 5.3 Payda etkisi (`ozet.json` → `payda_etkisi`, `payda_etkisi_yillik.csv`)

Koşul: takipteki tutar 4 çeyrekte reel olarak artıyor ama oran düşüyor.

- 5.022 il-çeyreğin **615'inde (%12,2)** bu durum var.
- Bu gözlemlerde medyan reel kredi büyümesi **%14,4**. Diğerlerinde **%6,4**.
- Yıllara göre: 2011–2015'te %15–30, 2016'da %5,6, 2017'de %26,5, 2019'da %1,5, 2021–2024'te %0–1.

Yani hızlı kredi büyümesi dönemlerinde oran sorunu gizliyor. E5 (takipteki tutarın reel değişimi) bu etkiden bağımsız, ama çeyrek etkisi orada daha da baskın (%71).

### 5.4 Öneri

**Ana etiket E3:** her çeyrekte ΔNPL₄'e göre en kötü %20'lik dilimdeki iller. Gerekçe:

1. Tanım gereği her yılda pozitif oranı %19,8. Tüm test yıllarında iki sınıf da var.
2. Döngüyü dışarıda bırakıyor ve doğrudan ekip sorusuna, "hangi il diğerlerinden daha çok kötüleşecek?" sorusuna yanıt veriyor.
3. Bölüm 6'da en çok sinyal taşıyan ikili tanım bu.

E2(0,5) eşiğe duyarlı ve yıllık oranı %3–43 arasında dalgalanıyor; modeller onda ROC 0,50 civarında kaldı.

Tamamlayıcı olarak sürekli göreli hedef ΔNPL₄ − TR (E4) ve sıralama metrikleri (Spearman, P@10) önerilir.

---

## 6. Fizibilite deneyi sonuçları

### Kurulum

**Doğrulama:**

- Expanding-window, test yılları 2016–2025 (2025 yalnızca Q1–Q2).
- Eğitim t ≤ test başlangıcı − 5 çeyrek. Yani 4 çeyrek boşluk var. Örnek: test 2016 → eğitim 2010Q1–2014Q4.

**Modeller:**

- B0: eğitimdeki pozitif oranı (sabit tahmin).
- B1: "son 4 çeyrekte NPL arttıysa 1". Sıralama skoru ΔNPL(t−4→t); göreli etiketlerde Türkiye'ye göre fark.
- B2: lojistik regresyon (C=0,1, medyan doldurma ve ölçekleme).
- B3: LightGBM. 8 kombinasyonlu ızgara (num_leaves, min_child_samples, n_estimators). Seçim, eğitimin son 4 çeyreğinde (önünde 4 çeyrek boşlukla) PR-AUC'ye göre yapıldı. Tohum 42.

**Özellikler:** `src/features.py`, 75 özellik: FinTürk 58, EVDS 8, komşu 4, TÜİK 5.

**Komşuluk:** `data/interim/il_komsuluk.csv`. TÜİK CİP `nuts3.json` sınırlarından shapely ile hesaplandı (0,001° tolerans). 199 il çifti; il başına 1–9 komşu (Kilis 1; Konya, Erzurum, Erzincan 9). Örnek kontroller doğru: İstanbul → Kırklareli, Kocaeli, Tekirdağ; Çanakkale → Balıkesir, Edirne, Tekirdağ. Ortak sınırı en kısa çiftler de gerçek komşular (Bolu–Çankırı, İstanbul–Kırklareli, Bilecik–Kocaeli).

### 6.1 Toplam metrikler, özellik seti iv (`metrik_ikili.csv`)

| Etiket | Model | PR-AUC | ROC-AUC | Brier | P@10 |
|---|---|---|---|---|---|
| **E3** (pozitif oranı 0,198) | B0 | 0,197 | 0,509 | 0,159 | 0,187 |
| | B1 | 0,226 | 0,559 | 0,466* | 0,268 |
| | B2 LR | 0,233 | 0,525 | 0,192 | 0,266 |
| | **B3 LGBM** | **0,247** | **0,575** | 0,162 | **0,324** |
| **E2 ≥0,5** (0,187) | B1 | 0,200 | 0,543 | 0,474* | 0,263 |
| | B2 LR | 0,164 | 0,451 | 0,263 | 0,226 |
| | B3 LGBM | 0,181 | 0,499 | 0,170 | 0,234 |
| **E1 ≥0,5** (0,290) | B0 | 0,211 | 0,329 | 0,222 | 0,295 |
| | B1 | 0,333 | 0,616 | 0,416* | 0,305 |
| | B2 LR | 0,428 | 0,555 | 0,438 | 0,300 |
| | B3 LGBM | 0,288 | 0,553 | 0,254 | 0,313 |

\* B1'in Brier değeri kuralın 0/1 çıktısıyla hesaplandı; olasılık değil.

Tek sınıflı test yılı **yok**. Ancak E1(0,5) 2022 test yılında 324 gözlemin yalnızca 1'i pozitif (%0,3) ve 2020'de %2,8. Bu yıllarda PR-AUC anlamsız.

**Yıl bazında** (`ozet.json` → `yil_bazinda_kazanc`, `figures/model_*_PR_AUC.png`):

| Etiket | LGBM > B1 (10 yılda) | LGBM > LR | LGBM − B1, yıllık PR-AUC farkının ort. ± std |
|---|---|---|---|
| E3 | 8 | 8 | +0,044 ± 0,067 |
| E2 ≥0,5 | 5 | 6 | +0,011 ± 0,048 |
| E1 ≥0,5 | 10 | 7 | +0,074 ± 0,076 |

**E1 için çelişkili görünen sonucun açıklaması:** Yıl içinde LightGBM her yıl B1'den iyi sıralıyor (10/10), ama yıllar birleştirildiğinde B1'in gerisinde kalıyor (0,288 < 0,333). Nedeni şu: LightGBM hangi yılın "sıcak" olacağını bilemiyor ve olasılık seviyesi yıllar arasında yanlış kalibre oluyor. B1 ise ülke döngüsünün kalıcılığını yakalıyor. Yani model yıl içinde **göreli** sıralamayı öğreniyor, döngüyü öğrenemiyor. Bu da E3 önerisini destekliyor.

### 6.2 Sürekli hedef E4 (`metrik_surekli.csv`)

| Hedef | Set | Model | MAE | Spearman (çeyrek içi ort.) |
|---|---|---|---|---|
| ΔNPL₄ | i | B1 son 4 çeyrek | 1,119 | 0,104 |
| | i | LGBM | 0,959 | 0,183 |
| | iv | LGBM | 1,046 | 0,141 |
| **ΔNPL₄ − TR** | i | B0 eğitim ort. | 0,547 | 0,003 |
| | i | B1 | 0,757 | 0,104 |
| | i | Ridge | 0,693 | 0,240 |
| | **i** | **LGBM** | **0,543** | **0,317** |
| | iv | LGBM | 0,570 | 0,192 |

- Göreli sürekli hedefte LightGBM (yalnızca FinTürk) çeyrek içi Spearman'da **0,32** alıyor. 10 test yılının 7'sinde 0,30'un üstünde; 2018'de 0,00, 2024'te 0,05.
- MAE açısından eğitim ortalamasını (0,547) zar zor geçiyor (0,543). Model büyüklüğü tahmin edemiyor, **sırayı** kısmen tahmin edebiliyor.
- Tüm özellikler eklenince (set iv) Spearman 0,19'a düşüyor. Gürültülü özellikler aşırı uyuma yol açıyor; özellik seçimi gerekli.

### 6.3 Ablation: LightGBM, toplam PR-AUC (`ablation.csv`, `figures/ablation_PR_AUC.png`)

| Set | E3 | E2 ≥0,5 | E1 ≥0,5 |
|---|---|---|---|
| (i) FinTürk | 0,233 | 0,181 | 0,291 |
| (ii) + EVDS | 0,228 (−0,005) | 0,184 (+0,004) | 0,298 (+0,008) |
| (iii) + komşu | 0,236 (+0,008) | 0,187 (+0,003) | 0,303 (+0,005) |
| (iv) + TÜİK | **0,247 (+0,011)** | 0,181 (−0,007) | 0,288 (−0,016) |
| B1 kuralı | 0,226 | 0,200 | 0,333 |

Yıl bazında, set iv ile set i arasındaki PR-AUC farkı: E3'te +0,019 ± 0,019, E1'de +0,023 ± 0,057. Eklemelerin hiçbiri yıllar arası standart sapmayı belirgin biçimde aşmıyor. **Katkılar gürültü düzeyinde.**

P@10 için set iv, E3'te 0,324; set i 0,263. Bu fark daha büyük, ama tek bir ölçüm.

---

## 7. Sızıntı denetimi

Model: son kat (test 2025, eğitim n=4.536), E3, set iv, parametreler num_leaves=7, min_child_samples=20, n_estimators=150. Kaynak: `onem_top25.csv` (gain ve SHAP ortalama |değer|, test kümesinde).

| # | Özellik | Gain payı | SHAP | t anında biliniyor mu? |
|---|---|---|---|---|
| 1 | npl_eksi_tr | 0,136 | 0,135 | Evet: NPL(t) − TR NPL(t), ikisi de t çeyreği FinTürk verisi |
| 2 | pay_toptan_ticaret | 0,045 | 0,067 | Evet: tablo 4 (t) / kredi (t) |
| 3 | kredi_mevduat | 0,044 | 0,106 | Evet: tablo 5 (t) |
| 4 | tuik_net_goc_hizi | 0,035 | 0,071 | Evet, **varsayımla**: Y yılı değeri Y+1 Mart'tan sonra kullanılıyor. Yayım tarihi doğrulanmadı; 6 aylık gecikmeyle yeniden denenmeli |
| 5 | perf_enerji | 0,031 | 0,084 | Evet: tablo 5 (t) |
| 6 | kk_takip_orani | 0,031 | 0,018 | Evet: tablo 3–4 (t) |
| 7 | m_reel_ihtiyac_faizi | 0,028 | 0,013 | Evet: çeyrek t ortalama faiz − yıllık TÜFE(t). Aylık veriler t+1 ayında yayımlanıyor; FinTürk(t)'den önce |
| 8 | subeye_dusen_nufus | 0,027 | 0,042 | Evet: tablo 6 (t) |
| 9 | npl_l2 | 0,026 | 0,058 | Evet: t−2 |
| 10 | tuik_konut_satis_b4 | 0,023 | 0,031 | Evet: yıllık değer, 2 ay gecikmeyle |
| 11 | npl_l8 | 0,022 | 0,071 | Evet: t−8 |
| 12 | npl_l1 | 0,022 | 0,044 | Evet: t−1 |
| 13 | perf_insaat | 0,021 | 0,063 | Evet: tablo 5 (t) |
| 14 | pay_diger_tuketici | 0,020 | 0,076 | Evet: tablo 3 (t) |
| 15 | pay_enerji | 0,020 | 0,023 | Evet: tablo 4 (t) |

Ek kontroller:

- Etiketten türetilmiş özellik yok. `dnpl4` ve `E*` sütunları özellik listesinde değil (`features.py` yalnızca `shift(k ≥ 0)` kullanıyor).
- Komşu özellikleri t anındaki değerlerden hesaplanıyor.
- İl ortalamasından sapma özelliği yalnızca geçmişe bakan (expanding) ortalamayla hesaplanıyor.
- LightGBM ızgara araması yalnızca eğitim katının içinde yapılıyor.
- Hiçbir metrik "fazla iyi" değil (en yüksek toplam ROC-AUC 0,616). Sızıntı belirtisi görülmedi.

**Kalan sızıntı riski:** TÜİK yayım gecikmeleri varsayım. FinTürk'ün kendi yayım gecikmesi yaklaşık 1–2 ay. Tahmin t+1–2 ayında yapılıyor ve etiket ufku buna göre fiilen yaklaşık 10–11 ay.

---

## 8. Karar tablosu

| # | Soru | Yanıt | Gerekçe |
|---|---|---|---|
| 1 | Ana veri eksiksiz ve tutarlı mı? | **Evet** | 81×66 = 5.346 tam, 0 tekrar, 0 muhasebe hatası; boşlukların tamamı 0/0; TÜFE kesintisi çözüldü (CV 2·10⁻⁶). Açık noktalar: 2010Q3 tanım şüphesi, 4 tek borçlu sıçraması |
| 2 | Anlamlı ve dengeli bir etiket var mı? | **Kısmen** | E3 her yıl %19,8 ve tüm yıllarda iki sınıf var. Ama planlanan E1(0,5)'te yıllık oran %0–82 ve 4 yıl tek sınıfa yakın. Etiket değişmeli |
| 3 | Model basit kuralları geçiyor mu? | **Kısmen** | E3: LGBM 0,247 vs B1 0,226, yani +%9,3 göreli (eşik %10), 8/10 yılda üstün. E1: toplamda geride (0,288 < 0,333), yıl içinde 10/10 üstün |
| 4 | İl düzeyinde sinyal var mı? | **Kısmen** | E3'te ROC 0,575, P@10 0,32 (rastgele 0,20). E2(0,5)'te sinyal yok (ROC 0,50). Sürekli göreli hedefte çeyrek içi Spearman 0,32 (B1 0,10) |
| 5 | TÜİK gerekli mi? | **Hayır** | Erişim var. Katkısı E3'te +0,011, E1'de −0,016 PR-AUC; yıllar arası std ±0,02. Proje TÜİK'siz yürür. EVDS'deki aylık il konut satışı daha güncel bir alternatif |
| 6 | GRU/TFT için veri yeterli mi? | **Hayır** | 5.022 etiketli gözlem; son katta 4.536 eğitim örneği; 81 kısa seri (≤62 çeyrek). LightGBM baseline'ı ancak %9 geçiyor. Derin modelden anlamlı kazanç beklemek için gerekçe yok |
| 7 | 7 ayda bitirilebilir mi? | **Evet** (değiştirilmiş kapsamla) | Veri boru hattı ve değerlendirme iskeleti hazır. Kalan iş Bölüm 9'da; GRU/TFT çıkarılırsa yaklaşık 45 iş günü |

### Karar: **DEĞİŞTİR**

1. **Etiket:** Mutlak E1(0,5)'i bırakın. Ana görev göreli sıralama olsun: E3 ve sürekli ΔNPL₄ − TR. Çünkü mutlak etiketin %58'i ülke döngüsü ve bu döngü 16 yılda 3–4 olayla öğrenilemiyor.
2. **Metrik:** P@10 ve çeyrek içi Spearman ana metrik olsun; PR-AUC ikincil kalsın. Bir erken uyarı sistemi zaten "bu çeyrekte izlenecek 10 il" listesi üretir.
3. **Kapsam:** GRU/TFT'yi zorunlu kapsamdan çıkarın. LightGBM + SHAP ve dürüst bir baseline karşılaştırması yeterli ve savunulabilir. Kazanılan süre veri temizliği ve açıklanabilirliğe gitsin.
4. **Veri:** Tek borçlu sıçramaları için bir kural ekleyin: bir sonraki çeyrekte geri dönen > 3 puanlık sıçramaları işaretleyin ya da kırpın. Kredi ağırlıklı değerlendirmeyi de raporlayın.
5. **Ek görev (Fikir 7, GNN ile kredi büyümesi):** Bu çalışmada **ölçülmedi**. Ancak kredi büyümesinin NPL'den daha az tek borçlu gürültüsü taşıması beklenir; bu bir varsayım. Aynı iskeletle 2 günlük bir fizibilite testi yapıldıktan sonra karar verilmeli.

---

## 9. Riskler ve önerilen sonraki adımlar (öncelik sırasıyla)

| # | İş | Tahmini iş günü | Not |
|---|---|---|---|
| 1 | Etiket kararını danışmanla netleştir (E3 / sürekli göreli) | 1 | Bölüm 10'daki sorular |
| 2 | Sıçrama temizleme kuralı ve kredi ağırlıklı metrikler; 2010Q3 kontrolü | 3 | Osmaniye, Amasya, Karaman, Kütahya örnekleri |
| 3 | FinTürk 2026-09'u ekle; aylık anlık görüntü düzeni (vintage) | 1 | finturk_indir.py'de BITIS parametresi |
| 4 | `evds.py`'de TÜFE kodunu TP.TUKFIY2025.GENEL yap; TÜFE ve sınır indirmelerini scriptlere taşı | 1 | |
| 5 | Özellik seçimi / düzenlileştirme; set iv'nin set i'den kötü çıktığı sürekli hedefte tekrarla | 4 | Bölüm 6.2 |
| 6 | Belirsizlik: yıllara göre bootstrap güven aralıkları; birkaç tohumla tekrar | 2 | Ablation farkları şu an gürültü düzeyinde |
| 7 | (İsteğe bağlı) Fikir 7 fizibilitesi: il kredi büyümesi hedefi, aynı iskelet | 2 | Kapsam kararı için |
| 8 | TÜİK yayım gecikmelerini bülten takviminden doğrula; EVDS aylık il konut satışlarını ekle | 2 | |
| 9 | SHAP açıklama sayfası; il bazında "neden riskli" kartı | 5 | |
| 10 | Backend (Express + PostgreSQL) şeması ve ETL | 8 | |
| 11 | React arayüzü: harita, il detay sayfası, çeyrek seçimi | 10 | |
| 12 | Rapor, sunum, tez yazımı | 8 | |
| | **Toplam (GRU/TFT hariç)** | **~47** | 3 kişi × 7 ay içinde rahat sığar |

**Riskler:**

- (R1) Sinyal zayıf. Sonuç "model kuralı az farkla geçiyor" olabilir. Bunu dürüst bir bulgu olarak sunmaya hazır olun.
- (R2) TÜİK ve EVDS uçları değişebilir (pytuik zaten hatalı çıktı).
- (R3) FinTürk revizyonları ölçülemedi.
- (R4) Tek borçlu olayları tahmin edilemez ve metrikleri yıl yıl oynatıyor.

---

## 10. Açık sorular

**Ekonomi hocasına:**

1. İl NPL'sinde tek büyük borçlunun takibe girmesi (Osmaniye 2024-09'da metal sektörü 8 milyar TL, bir çeyrek sonra geri döndü) nasıl ele alınmalı? Bu bir veri hatası mı, takipten çıkış (satış ya da aktiften silme) mı?
2. Takipteki alacak satışları ve aktiften silmeler NPL'yi düşürüyor. İl bazında bu etkiyi ayırmanın bir kaynağı var mı?
3. 2010-09'da 13 ilde kredilerin %30–137 artmasının bilinen bir tanım ya da raporlama değişikliğiyle ilişkisi var mı?
4. Göreli risk (ilin ülkeye göre kötüleşmesi) bir banka ya da düzenleyici için anlamlı bir erken uyarı sorusu mu, yoksa mutlak eşik mi esas alınmalı?

**Danışmana:**

1. Hedef sorunun "hangi iller diğerlerinden daha çok kötüleşecek" olarak değiştirilmesi bitirme projesi kapsamında kabul edilir mi?
2. GRU/TFT'nin kapsamdan çıkarılması ya da yalnızca negatif sonuçlu bir karşılaştırma olarak kalması uygun mu?
3. Fikir 7 (GNN ile kredi büyümesi) ikinci görev olarak eklenmeli mi?

---

## 11. Doğrulanamayanlar

- 31 Ekim'deki TÜİK erişim sorununun nedeni. 1 Kasım'da sorun yoktu.
- TÜİK SDMX'in anonim isteklere 401 verdiği bilgisi (test edilmedi).
- TÜİK göstergelerinin yayım gecikmeleri (2–12 ay varsayımları).
- FinTürk'ün kesin yayım takvimi (1–2 ay bulgusu dolaylı).
- FinTürk'te uzun vadeli revizyon olup olmadığı (yalnızca 2 günlük karşılaştırma yapıldı).
- Osmaniye 2024-09 ve Amasya 2015-03 sıçramalarının veri hatası mı gerçek olay mı olduğu.
- 2010-09 kredi sıçramasının tanım değişikliği olup olmadığı.
- CİP'te SES skorunun neden boş geldiği.
- CİP'te il bazında ihracat göstergesi olmaması. Başka bir TÜİK tablosunda olabilir, aranmadı.
- Kalkınma Ajansı ve SBB yayınları açılmadı.
- IPv6 erişimi (AAAA kaydı yok).
- Fikir 7'nin (kredi büyümesi görevi) öğrenilebilirliği. Ölçülmedi.

---

## 12. Kaynaklar (bu çalışmada açılan adresler)

**TÜİK**

- https://cip.tuik.gov.tr/ , https://data.tuik.gov.tr/ , https://veriportali.tuik.gov.tr/ , https://nsiws.tuik.gov.tr/ , https://www.tuik.gov.tr/ (ağ teşhisi)
- https://cip.tuik.gov.tr/assets/sideMenu.json?v=2.000 (CİP kataloğu)
- https://cip.tuik.gov.tr/Home/GetMapData (gösterge verileri; parametreler: kaynak, duzey, gostergeNo, kayitSayisi, period)
- https://cip.tuik.gov.tr/assets/geometri/nuts3.json (il sınırları, İBBS eşlemesi)
- veriportali tema 6 tablo listesi (pytuik `get_tables(6)`), ardından:
  - TÜFE 2003=100: https://veriportali.tuik.gov.tr/api/tr/data/downloads?t=i&p=c1ds34bfL%2BIKJqXmjoTX6bTbCw7McpRDG8%2B3EpQnA2aJ8BiuQ415QEmFTSwjjkfFvFabUSZAruCfjSD5TZmGYuLaU9dnzDAfQMWNGDTLGz0%3D
  - TÜFE 2025=100: https://veriportali.tuik.gov.tr/api/tr/data/downloads?t=i&p=TWbHpfWMMIhgV3%2FlUrizwFgqtq%2FRCxvsg37y9qvh6OpWu0oeeMsJ%2B0Hv0tOJ4FRJ6wZX27kDn4NAftxG40YKUeh7eaXTEPrarhUCrLOs9NE%3D
  - Not: Bu indirme bağlantıları oturuma özgü olabilir; kalıcılıkları doğrulanmadı.

**TCMB EVDS** (`key` başlığıyla)

- https://evds3.tcmb.gov.tr/ (ağ teşhisi)
- https://evds3.tcmb.gov.tr/igmevdsms-dis/categories/type=json
- https://evds3.tcmb.gov.tr/igmevdsms-dis/datagroups/mode=2&code=<kategori>&type=json (10 kategori)
- https://evds3.tcmb.gov.tr/igmevdsms-dis/serieList/type=json&code=<veri grubu>
- https://evds3.tcmb.gov.tr/igmevdsms-dis/series=TP.TUKFIY2025.GENEL / TP.GENENDEKS.T1 / TP.FG.J0 (veri)

**BDDK**

- https://www.bddk.org.tr/ (ağ teşhisi)
- https://www.bddk.org.tr/BultenFinturk/tr/Home/VeriGetir (pybrsa üzerinden; revizyon kontrolü ve 2026-09 testi)
