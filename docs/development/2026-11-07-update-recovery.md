# Güncelleme ve geri dönüş güvenilirliği — 7 Kasım 2026

Başlangıç: main `25ff36a3564a2b239488d7e98b2a7bff60df63fb` (4.6.47).
Dal: `feature/night-update-recovery-20261107`.
Başlangıçta açık PR yoktu; depoda AGENTS.md veya önceki gece raporu bulunmadı.

## Düzeltilen sorunlar

- Geri dönüş API'sinin hata sonucu panelde yok sayılıyor, olmayan yedek için bile yeniden başlatma bekleniyordu. Artık hata gösterilir, işlem düğmeleri yeniden etkinleşir; ağ hatası da yakalanır.
- Güncelleme sonrası HTTP yerel adres zorla HTTPS'e çevriliyordu. Mevcut adres yeniden yüklenir. Yeni sürüm numarası da kontrol edildiğinden kısa yeniden başlatma kesintisini kaçırmak 60 saniye beklemeye neden olmaz.
- Yeniden başlatma sorguları erişim anahtarını taşır, dört saniyede iptal edilir ve üst üste binmez. Başarıda zamanlayıcılar temizlenir, geç kalan süre sınırı ikinci kez sayfayı yenilemez.
- Geç kalan ilerleme yanıtları başarı mesajını ezemez. Panel işlem sürerken ikinci bir güncelleme/geri dönüş veya sürüm kontrolü başlatmaz.
- Sunucudaki geri dönüş aynı güncelleme kilidini kullanır. İşlem sürerken ikinci geri dönüş veya güncelleme dosyalara yazmaz. Bozuk yedek hatası yapılandırılmış sonuç ve durum bilgisi üretir, yeniden başlatma yapılmaz ve kilit serbest kalır.

## Doğrulama

- `python tests/test_update_recovery.py`: 4 test geçti. Eksik/bozuk yedek ve iki yönde eşzamanlı yazma engeli doğrulandı.
- `node tests/test_update_ui.js`: gerçek update.js kodunu sahte DOM, ağ ve denetlenebilir zamanlayıcılarla çalıştıran regresyonlar geçti. Hata görünümü, düğmeler, çift işlem engeli, erişim anahtarı, HTTP adresinin korunması, kısa kesintiyi kaçırma, geç ilerleme sonucu, sorgu çakışması ve zamanlayıcı temizliği sınandı.
- `python tests/test_update.py`: 14 kontrol geçti. Yerel sahte GitHub ve gerçek JARVIS sunucusunda bozuk sürümün reddi, güncelleme, gözetmenle yeniden başlatma, .env/hafıza/eklenti korunması, eski kod temizliği, yedek ve geri dönüş başarılı.
- `node --check web/update.js` ve `git diff --check`: geçti.

## Sınırlar ve sonraki oturum

Linux ortamında doğrulandı; Windows kullanıcı cihazında ve gerçek tarayıcıyla görsel test yapılmadı. Canlı Gemini/API anahtarı veya SpacePlanner hesabı kullanılmadı. Gemini kotası/model davranışı, ses ve SpacePlanner bu değişiklikte değiştirilmedi. Sürüm metadata'sı korunarak incelemeye hazır PR hazırlanır; main'e birleştirme veya yayın yapılmaz. Sonraki oturum önce açık PR/dal durumunu kontrol etmeli; bu çalışmayı tekrar etmeden diğer önceliklerden kanıtlanabilir bir sorun seçmeli.
