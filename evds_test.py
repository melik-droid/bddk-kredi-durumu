"""
TCMB EVDS API bağlantı testi.
Çalıştır:  python3 evds_test.py   (API anahtarını soracak, ekrana yazmaz)
"""
import getpass
import requests

API_KEY = getpass.getpass("EVDS API anahtarı: ").strip()

SERILER = {
    "TP.DK.USD.A.YTL": "USD/TL döviz alış kuru (günlük)",
    "TP.FG.J0": "TÜFE genel endeks (aylık)",
}
BAS, BIT = "01-01-2024", "31-03-2024"   # gg-aa-yyyy

# EVDS'nin bilinen iki adresi; hangisi cevap verirse onu kullanacağız
ADRESLER = [
    "https://evds3.tcmb.gov.tr/igmevdsms-dis/",
    "https://evds2.tcmb.gov.tr/service/evds/",
]

for kod, ad in SERILER.items():
    print(f"\n=== {kod}  ({ad}) ===")
    for adres in ADRESLER:
        url = f"{adres}series={kod}&startDate={BAS}&endDate={BIT}&type=json"
        try:
            r = requests.get(url, headers={"key": API_KEY}, timeout=30)
        except requests.RequestException as e:
            print(f"  {adres} -> bağlantı hatası: {e}")
            continue
        if r.status_code != 200:
            print(f"  {adres} -> HTTP {r.status_code}")
            continue
        try:
            items = r.json().get("items", [])
        except ValueError:
            print(f"  {adres} -> JSON değil, ilk 200 karakter: {r.text[:200]!r}")
            continue
        print(f"  {adres} -> OK, {len(items)} gözlem")
        for satir in items[:5]:
            print("   ", satir)
        break