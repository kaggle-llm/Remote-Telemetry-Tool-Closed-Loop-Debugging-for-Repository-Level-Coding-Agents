# Gemma 4 Ajanı Aracı Nasıl Çağırır? (Tool Calling Mechanics)

Gemma 4 gibi açık ağırlıklı ajan modelleri, harici araçları (tools) **Google Agent Development Kit (ADK)** ve standart **Function Calling** mekanizması aracılığıyla otonom olarak çalıştırır. Süreç adım adım şöyledir:

## 1. Konfigürasyon Tanımı (`agent.yaml`)
Ajanın erişebileceği tüm araçlar `agent.yaml` dosyasında fonksiyon imzaları ve açıklamalarıyla belirtilir:
```yaml
tools:
  - name: fetch_client_logs
    description: Fetch runtime crash logs and telemetry from remote iOS/client applications stored in Supabase.
    entrypoint: telemetry_tool.py:fetch_client_logs
```

## 2. Kullanıcı İstemi (User Prompt)
Kullanıcı ajana şu görevi verir:
> *"Find why the iOS app is crashing and fix the bug."*

## 3. Modelin Niyet Tespiti (Tool Call Generation)
Gemma 4 modeli, sistem promptunu ve araç tanımlarını okuyarak uzaktaki istemci loglarına ihtiyacı olduğunu anlar ve arka planda bir tool çağrısı üretir:
```json
{
  "tool": "fetch_client_logs",
  "arguments": {
    "limit": 5
  }
}
```

## 4. Harness Tarafından Çalıştırma ve Geri Besleme
* Google ADK harness'ı bu JSON isteğini yakalar.
* `telemetry_tool.py` içindeki `fetch_client_logs(limit=5)` fonksiyonunu Python ortamında çalıştırır.
* Fonksiyondan dönen log verisi (JSON formatında) modelin bağlamına (context) geri beslenir:
  ```json
  [
    {
      "id": 1,
      "client": "ios_app_v1.0",
      "level": "ERROR",
      "message": "Crash in UserProfileView: force unwrap optional nil at line 42"
    }
  ]
  ```

## 5. Otonom Eylem (Action & Patch)
Ajan logdaki hata mesajını okur, kod tabanında ilgili görünüm dosyasını bulur (`grep` / `read`), gerekli düzeltmeyi yapar ve çözümü tamamlar.
