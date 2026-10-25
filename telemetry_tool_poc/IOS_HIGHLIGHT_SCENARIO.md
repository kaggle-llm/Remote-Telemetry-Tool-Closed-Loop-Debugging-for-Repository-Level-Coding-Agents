# Örnek Senaryo: iOS Highlight Renk Paleti Açılmıyor

Bu senaryo, bir iOS uygulamasında kullanıcıların metin vurgulama (highlight) renk paletinin açılmaması sorununu, uzaktan log toplama ve Gemma 4 ajanının otonom müdahale döngüsünü adım adım açıklar.

## Adım 1: Kullanıcı Tarafındaki Hata ve Loglama
1. **Olay:** iOS kullanıcısı uygulamada metin seçer ve highlight butonuna basar, ancak renk paleti açılmaz (UI state kilitlenir veya event tetiklenmez).
2. **Otomatik Log (Supabase):** iOS uygulamasındaki hata yakalama mekanizması durumu algılar ve Supabase `client_logs` tablosuna şu kaydı atar:
   ```json
   {
     "client_id": "ios_app_v1.2",
     "level": "ERROR",
     "message": "HighlightPaletteView failed to present: ViewModel state is nil when selecting color.",
     "metadata": {"view": "HighlightPaletteView", "action": "open_palette"}
   }
   ```

## Adım 2: Ajanın Tetiklenmesi ve Araç Çağrısı (Tool Calling)
1. **İstek:** Geliştirici, Gemma 4 ajanına komut verir: *"Check recent remote client errors and fix the highlight palette bug."*
2. **Tool Çağrısı:** Ajan, `fetch_client_logs` aracını çalıştırarak Supabase'deki son logları çeker.

## Adım 3: Kod Analizi ve Sorunun Tespiti
1. **Ajanın İncelemesi:** Ajan logdaki mesajı okur: `"HighlightPaletteView failed to present: ViewModel state is nil"`.
2. **Dosya Arama:** Ajan repoda `HighlightPaletteView.swift` dosyasını bulur (`grep` / `read`).
3. **Kod İncelemesi:** Swift kodunda `presentPalette()` fonksiyonunun view model'in yüklenmesini beklemeden çalıştığını ve opsiyonel `nil` patlamasına yol açtığını tespit eder.

## Adım 4: Otonom Düzeltme ve Log Entegrasyonu (Patching & Instrumentation)
1. **Kod Düzeltmesi:** Ajan güvenli kontrol (`guard let`) ekleyerek paletin açılmamasını engeller.
2. **Proaktif Loglama:** Ajan, ileride benzer bir durum olursa diye koda otomatik hata loglama ekler:
   ```swift
   guard let viewModel = self.viewModel else {
       SupabaseClient.shared.log(level: "WARNING", message: "HighlightPaletteView: ViewModel was nil during presentation attempt.")
       return
   }
   ```
3. **Test ve Doğrulama:** Ajan testleri çalıştırır ve yamayı tamamlar.
