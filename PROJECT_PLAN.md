# Google - The Gemma 4 Developer Agent Paper Track: Proje Analizi ve Yol Haritası

## 1. Proje Amacı (The Goal)
**Google - The Gemma 4 Developer Agent Paper Track** yarışmasının temel amacı, devasa bulut tabanlı API modellerine bağımlı kalmadan, **Gemma 4** açık ağırlıklı (open-weight) modellerini (özellikle `gemma-4-31b`, `12b`, `e4b`, `e2b` QAT W4A16 varyantları) günlük tüketici donanımında veya çevrimdışı ortamlarda çalışabilecek **özerk yazılım mühendisliği ajanlarına (autonomous software engineering agents)** dönüştürmektir.

Paper Track (Makale Kulübü/Pistinin) amacı ise kodlama lider tablosundan bağımsız olarak; bu süreçteki yöntemleri, fine-tuning/RL yaklaşımlarını, kod anlama/görselleştirme tekniklerini, deneyleri ve analizleri içeren orijinal bir araştırma makalesi (Kaggle Writeup, max 3,000 kelime) sunmaktır.

---

## 2. İstenenler (Requirements & Deliverables)
* **Araştırma Yazısı (Kaggle Writeup / PDF):** En fazla 3.000 kelimeden oluşan; Özet, Giriş, Yöntemler, Deneyler, İlgili Çalışmalar ve Sonuç bölümlerini içeren özgün araştırma metni.
* **Değerlendirme Kriterleri (0-5 Puan):**
  1. *Yenilik (Novelty):* Mevcut yöntemlere kıyasla yeni içgörüler ve katkılar.
  2. *Kalite (Quality):* Yaklaşımın yarışma dışına genelleştirilebilirliği.
  3. *İlgililik (Relevance):* Yazılım mühendisliği ve ajan öğrenimi için önemi.
  4. *Doğrulanabilirlik (Verifiability):* Deneylerin, verilerin ve metotların şeffaflığı.
  5. *Açıklık (Clarity):* Makalenin anlatım ve yapı kalitesi.
* **Ödül Kategorileri:**
  * *Overall Best Paper* ($15,000)
  * *Best New Resource* ($10,000 - Veri seti, araç, kütüphane vb.)
  * *Best New Application* ($10,000 - Yeni kullanım alanı / uygulama)

---

## 3. Adım Adım Plan (Step-by-Step Plan)

### Adım 1: Araştırma Odağının Seçilmesi (Research Focus Selection)
* **Seçenek A (Tuning & PEFT/RL):** Gemma 4 küçük/büyük modelleri üzerinde QLoRA / Test-Feedback-Driven (TFD) fine-tuning optimizasyonları.
* **Seçenek B (Code Comprehension & Graph Reasoning):** Büyük repolarda kod grafiği (code-graph) analizi, simge arama ve token bütçesi yönetimi.
* **Seçenek C (Small Model Efficiency):** Gemma E4B veya E2B modelleri ile uç cihazlarda (edge/consumer hardware) yüksek performanslı ajan davranışı.

### Adım 2: Deney Altyapısının Kurulması (Environment & Harness Setup)
* Google ADK (Agent Development Kit) ve vLLM tabanlı yerel test ortamının hazırlanması.
* Açık kaynaklı veri setlerinin (ör. TFD trajectories, run logs) incelenmesi ve yerel simülasyonların çalıştırılması.

### Adım 3: Deneylerin Koşulması ve Metriklerin Toplanması (Execution & Benchmarking)
* Seçilen hipotez doğrultusunda ajan denemelerinin yapılması (başarı oranları, tool-call hataları, context overflow durumları).
* Sonuçların CSV/JSON formatında toplanıp görselleştirilmesi (Grafikler ve tablolar).

### Adım 4: Makale Taslağının Yazılması (Drafting the Writeup)
* Abstract, Introduction, Methodology, Experiments, Discussion ve Conclusion bölümlerinin 3.000 kelimeyi aşmayacak şekilde yapılandırılması.
* Şekil ve tabloların eklenmesi.

### Adım 5: Son Kontroller ve Kaggle Gönderimi (Final Review & Submission)
* Yazımın 5 değerlendirme kriterine göre (Novelty, Quality, Relevance, Verifiability, Clarity) optimize edilmesi.
* Kaggle Paper Track platformuna yüklenmesi (Son tarih: **12 Kasım 2026**).
