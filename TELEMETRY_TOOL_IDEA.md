# Proje Fikri: Supabase Destekli Uzaktan Loglama ve Telemetri Ajan Aracı (Remote Telemetry Tool)

## 1. Fikrin Özü
Lokal ortamda Gemma 4 gibi açık ağırlıklı modellerle geliştirme yaparken, yapay zeka ajanlarının doğrudan erişemediği **iOS/Android istemcileri, mobil uygulamalar veya uzak uç cihazlardaki** çalışma zamanı (runtime) loglarını ve hata izlerini toplayıp ajana sunan özel bir **Tool (Araç)** geliştirmek.

---

## 2. Problem ve İhtiyaç
* **Erişim Kısıtı:** Ajanlar yerel repolarda ve test ortamlarında çalışır; ancak kullanıcıların mobil cihazlarında (iOS client) koşan uygulamalardaki anlık çöküşleri ve logları doğrudan göremezler.
* **Kör Nokta:** Uzak cihazlardan gelen hataların manuel olarak kopyalanıp ajana aktarılması süreci yavaşlatır ve otonom döngüyü (autonomous loop) kırar.

---

## 3. Çözüm Mimarisi (`RemoteTelemetryTool`)
1. **Supabase Entegrasyonu:** Mobil istemciler (örn. iOS app), hata ve çalışma zamanı loglarını hafif bir Supabase veritabanına (Realtime / REST API üzerinden) güvenli bir şekilde yazar.
2. **Özel Ajan Aracı (Custom ADK Tool):** Gemma 4 ajanının konfigürasyonuna (`tools/` veya `agent.yaml`) eklenen özel bir araç (`fetch_client_logs`).
3. **Otonom Sorgulama:** Ajan, kod tabanında bir değişiklik yaptıktan veya uzak cihazlardan hata bildirimi geldiğinde bu aracı çağırarak güncel istemci loglarını çeker, hatanın kaynağını analiz eder ve otonom olarak düzeltme (patch) üretir.

---

## 4. Paper Track İçin Değeri
* **Best New Resource / Best New Application** kategorileri için mükemmel bir adaydır.
* Yerel (Edge) ajanların sadece dosya sistemiyle değil, bulut/veritabanı köprüleriyle uzak uç cihazlardan telemetri toplayarak yazılım mühendisliği yeteneklerini nasıl genişletebileceğini kanıtlar.
