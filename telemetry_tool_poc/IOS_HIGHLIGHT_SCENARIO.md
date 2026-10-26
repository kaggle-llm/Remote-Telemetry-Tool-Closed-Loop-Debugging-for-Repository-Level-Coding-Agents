# Örnek Senaryo: iOS Highlight Renk Paleti Açılmıyor

Bu senaryo, bir iOS uygulamasında kullanıcıların metin vurgulama (highlight) renk paletinin açılmaması sorununu, **kapalı döngülü (closed-loop) telemetri protokolü** ile uçtan uca anlatır. Her adım karşılığında çalışan bir endpoint ve bir aracı (tool) vardır.

| # | Adım | Aktör | Endpoint / Tool |
|---|---|---|---|
| 1 | Normal durum: hata yok, log yok | — | — |
| 2 | Kullanıcı hatayı görüyor ve AI'ye bildiriyor | Kullanıcı | `POST /api/client/cases` |
| 3 | AI kodda akıllı loglama yapıyor, cihazda olay takibi | AI | `request_instrumentation` |
| 4 | AI geri bildirim gönderiyor, tekrar denemesini bekliyor | AI → Kullanıcı | `await_user_recheck` + `POST /api/client/cases/:id/state` |
| 5 | Kullanıcı tekrar kontrol edip AI'ye bildiriyor | Kullanıcı | `POST /api/client/cases/:id/report` |
| 6 | AI logları analiz ediyor, patch uyguluyor | AI | `fetch_case_logs` + `finalize_case` |
| 7 | Kullanıcı onaylarsa loglar koddan ve DB'den temizleniyor | Kullanıcı + AI | `approve_case` + `cleanup_case` |

## Adım 1: Normal Durum

Varsayılan durumda cihaz **hiçbir şey loglamaz**. Uygulama yalnızca `case_probes` tablosunda aktif bir probe bulunduğunda olay toplar. Bu, hem maliyet/vergi tabanını düşürür hem de "log yakalama yok" varsayımını teknik olarak mümkün kılar.

## Adım 2: Kullanıcı Hatayı Bildiriyor

Kullanıcı (cihazı elinde tutan kişi) hatayı uygulamadan bildirir:

```json
POST /api/client/cases
{
  "session_key": "tcs_...",
  "title": "Highlight palette does not open",
  "user_report": "I select text and tap highlight, but the color palette never appears."
}
```

Sunucu `debug_cases` satırı oluşturur ve durumu `reported` yapar. Kullanıcının metni serbest metindir; hem sunucu hem Python aracı tarafından e-posta/adres kalıpları temizlenir.

> Not: Uç kullanıcının hesap kimliği yoktur. Cihazın `tcs_` client session anahtarı, o cihazı (dolayısıyla onu kullanan kişiyi) temsil eder ve onay yetkisi bu anahtardan gelir. Geliştirici `users` tablosundaki Google hesabıdır; ikisi karıştırılmamalıdır.

## Adım 3: AI Akıllı Loglama Yapıyor

AI, hangi olayın toplanacağını **veri olarak** bildirir — kör satır içi log kodu yazmaz:

```json
request_instrumentation(
  case_id = "...",
  instructions = "Reproduce the highlight flow and confirm the palette opens after the guard is applied.",
  probes = [{
    "probe_id": "palette_context",
    "target": "HighlightPaletteView.presentPalette",
    "capture": { "presentation_context": "true", "viewmodel_state": "true" },
    "level": "warn"
  }]
)
```

Uygulama probe'ları çalışma zamanında uygular; toplanan her olay `client_logs.case_id` ile bu case'e bağlanır. Durum `instrumenting` olur.

**Neden runtime probe?** AI'ın kodu değiştirmesi her iterasyonda yeniden build/deploy gerektirir; bu, otonom döngüyü kırar. Probe modeli enstrümantasyonu dağıtımdan ayırır.

## Adım 4: AI Geri Bildirim Gönderiyor

AI, kullanıcıya ne yapması gerektiğini söyler ve tekrar denemesini bekler:

```json
await_user_recheck(
  case_id = "...",
  instructions = "Please select text and tap highlight again. The palette should now open."
)
```

Durum `awaiting_recheck` olur. Cihaz `POST /api/client/cases/:id/state` ile durumu ve talimatları yoklar (push altyapısı gerekmez; sürüm numarası ile değişiklik algılanır). Kullanıcı talimatı görür ve işlemi tekrarlar.

## Adım 5: Kullanıcı Tekrar Kontrol Ediyor

Kullanıcı cihazda tekrar dener ve sonucu bildirir:

```json
POST /api/client/cases/:id/report
{
  "session_key": "tcs_...",
  "report": "Re-checked: the palette now opens and shows the yellow highlight."
}
```

Sunucu raporu `user_report` zaman çizelgesine ekler ve durumu `rechecked` yapar. Bu RPC yalnızca `awaiting_recheck` durumundan çalışır; AI istemeden önce rapor gönderilemez.

## Adım 6: AI Logları Analiz Ediyor ve Patch Uyguluyor

AI yalnızca **bu case'e ait** logları okur:

```json
fetch_case_logs(case_id = "...", limit = 50)
```

Hesap genelindeki tüm logları okumak yerine case kapsamlı okuma, yanlış olaya patch uygulama riskini ve bağlam kirliliğini ortadan kaldırır. AI repo'yu inceler, en olası kök nedeni test eder ve minimal patch'i önerir.

Ardından:

```json
finalize_case(case_id = "...")
```

Durum `patch_ready` olur. Bu geçiş yalnızca `rechecked` durumundan yapılabilir; AI, kullanıcı doğrulaması olmadan "düzeltildi" diyemez.

## Adım 7: Onay ve Temizlik

Kullanıcı çözümü onaylar:

```json
POST /api/client/cases/:id/approve
{ "session_key": "tcs_...", "approved": true }
```

Durum `approved` olur. **Ancak onaydan sonra** AI temizlik yapabilir:

```json
cleanup_case(case_id = "...")
```

Bu işlem:
1. Yalnızca o case'e ait `client_logs` satırlarını siler,
2. Case'i `resolved` durumuna alır,
3. Probe'ları pasifleştirir (cihazda artık olay toplanmaz).

`purge_case_logs` yalnızca `approved` durumundan çalışır; onaysız temizlik mümkün değildir. `debug_cases` satırı denetim izi olarak kalır.

## Özet: Döngünün Dayandığı Üç Tasarım Kararı

1. **Durum makinesi sunucuda zorlanır.** Hem Express katmanı hem Supabase RPC'leri geçişleri denetler; ajan bir aşamayı atlamaya çalışırsa hata alır, tutarsız kayıt oluşmaz.
2. **Enstrümantasyon geri alınabilirdir.** Probe'lar veri olarak tanımlandığı için kaldırma deterministiktir; "koddan logları temizle" adımı somut bir işlemdir.
3. **Kanıt kapsamı case'e bağlıdır.** `client_logs.case_id` sayesinde her okuma tek bir hata denemesine aittir.

## Uçtan Uca Çalıştırma

Canlı döngüyü doğrulayan senaryo betiği:

```powershell
python -m ai_client_demo.debug_loop_demo
```

Betik 7 adımı sırayla yürütür, adım 7'den önce case'e bağlı log sayısını ve temizlikten sonra silinen log sayısını raporlar ve hiçbir sırrı ekrana basmaz.
