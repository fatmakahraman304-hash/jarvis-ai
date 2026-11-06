# Özellik durumu — v4.6.37

Ev tasarımı yalnızca SpacePlanner sitesinde yapılır. Yerel mimari editör ve PLAN / ARAÇLAR sekmesi kullanıcı isteğiyle kodlarıyla birlikte kaldırıldı.

| No | İstenen özellik | Durum | Gerçek kapsam / eksik |
|---|---|---|---|
| 9 | Gelişmiş gürültü/yankı engelleme | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 10 | Ses tonundan güvenilir duygu tespiti | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 11 | Özel fısıltı algılama | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 12 | Tam çevrimdışı konuşma tanıma | Kurulum/canlı test gerekli | Vosk yerel model yolu gerektirir. WAV tanıma ve sürekli uyandırma hattı eklendi; buluta yedek geçmez. Gerçek mikrofon/dil modeli testi kullanıcı cihazında yapılmalı. |
| 13 | Mikrofon/hoparlör otomatik yönetimi | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 22 | GPT/Gemini/Claude/yerel doğrudan bağlantıları | Kısmi | GPT ve Anthropic uyumlu Chat Completions uçları eklendi; Gemini/Ollama mevcut. Hesap anahtarları ve canlı sağlayıcı testleri gerekli; tüm API özellikleri kapsanmaz. |
| 23 | İnternet bilgisini çapraz doğrulama | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 24 | Birden fazla model cevabını karşılaştırma | Kısmi | En fazla dört modele aynı soru yöneltilir; yanıtlar ve kimlikler ayrı döner. Bağımsız doğruluk kanıtı değildir. |
| 25 | Gelişmiş yanlış bilgi önleme | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 67 | Eksiksiz tarayıcı dosya aktarımı | Kısmi | File input yükleme ve indirme olayını yakalama eklendi. Özel dropzone/yerel dosya diyalogu gibi tüm türler kapsanmaz. |
| 68 | Bağımsız otomatik bilgi doğrulama | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 94 | Eksiksiz duvar çizme/düzenleme | Kısmi | İşlemler yalnızca kontrollü SpacePlanner sitesinin gerçek arayüzünden yapılır; tüm tasarımlar canlı olarak doğrulanmadı. Yerel mimari editör kullanıcı isteğiyle kaldırıldı. |
| 95 | Otomatik kapı/pencere yerleştirme | Kısmi | İşlemler yalnızca kontrollü SpacePlanner sitesinin gerçek arayüzünden yapılır; tüm tasarımlar canlı olarak doğrulanmadı. Yerel mimari editör kullanıcı isteğiyle kaldırıldı. |
| 96 | Eksiksiz mobilya yerleştirme | Kısmi | İşlemler yalnızca kontrollü SpacePlanner sitesinin gerçek arayüzünden yapılır; tüm tasarımlar canlı olarak doğrulanmadı. Yerel mimari editör kullanıcı isteğiyle kaldırıldı. |
| 97 | Yerel mimari mobilya kütüphanesi | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 98 | Profesyonel ölçülü mimari plan | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 99 | Otomatik metrekare hesabı | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 100 | Tam kat planı editörü | Kısmi | İşlemler yalnızca kontrollü SpacePlanner sitesinin gerçek arayüzünden yapılır; tüm tasarımlar canlı olarak doğrulanmadı. Yerel mimari editör kullanıcı isteğiyle kaldırıldı. |
| 101 | Merdiven/balkon/teras editörü | Kısmi | İşlemler yalnızca kontrollü SpacePlanner sitesinin gerçek arayüzünden yapılır; tüm tasarımlar canlı olarak doğrulanmadı. Yerel mimari editör kullanıcı isteğiyle kaldırıldı. |
| 102 | Özel mutfak/banyo tasarımı | Kısmi | İşlemler yalnızca kontrollü SpacePlanner sitesinin gerçek arayüzünden yapılır; tüm tasarımlar canlı olarak doğrulanmadı. Yerel mimari editör kullanıcı isteğiyle kaldırıldı. |
| 103 | Mimari malzeme/kaplama kataloğu | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 104 | Fotogerçekçi mimari ışıklandırma | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 105 | Güneş/gölge analizi | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 106 | 3D ev içinde gezinti | Kısmi | İşlemler yalnızca kontrollü SpacePlanner sitesinin gerçek arayüzünden yapılır; tüm tasarımlar canlı olarak doğrulanmadı. Yerel mimari editör kullanıcı isteğiyle kaldırıldı. |
| 107 | Mobilya çakışma kontrolü | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 108 | Otomatik oda yerleşimi | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 109 | Fotoğraftan ölçekli plan | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 110 | DWG/DXF/OBJ/GLB/PDF aktarımının tamamı | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 111 | Fotogerçekçi render | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 112 | Sesle tüm mimariyi güvenilir değiştirme | Kısmi | İşlemler yalnızca kontrollü SpacePlanner sitesinin gerçek arayüzünden yapılır; tüm tasarımlar canlı olarak doğrulanmadı. Yerel mimari editör kullanıcı isteğiyle kaldırıldı. |
| 113 | Alternatif ev planları | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 114 | Elektrik/tesisat planlama | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 115 | Malzeme metrajı/maliyet | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 116 | Tam yerel proje kayıt/sürüm sistemi | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 117 | SpacePlanner seviyesinde bağımsız editör | Bekliyor | Yerel mimari araç uygulanmaz; kullanıcı isteğiyle kodları kaldırıldı. SpacePlanner sitesindeki gerçek özellikler tarayıcı üzerinden kullanılabilir; yerel özellik olarak sayılmaz. |
| 133 | Kapsamlı güvenlik açığı tarayıcısı | Kısmi | Sezgisel Python AST kaynak denetimi eklendi; tam CVE/dinamik zafiyet tarayıcısı değil. |
| 134 | Genel veritabanı yönetim paneli | Kısmi | Salt okunur SQLite tablo/satır inceleme aracı var; genel veritabanı yönetim paneli yok. |
| 148 | Her güncelleme hatasını otomatik tekrar deneme | Kısmi | Geçici HTTP/ağ hatalarında üç indirme denemesi, paket kurulumunda iki sınırlı deneme ve süre sınırı eklendi. Yetki/sözdizimi/kalıcı test hataları körlemesine tekrar edilmez. |
| 149 | Kriptografik güncelleme imzası | Bekliyor | Güvenilen yayın imzalama anahtarı, imzalı paket üretimi ve güncelleyiciye zorunlu doğrulama hattı kurulmadı. |
| 164 | Ayrıntılı enerji analizi | Kısmi | Watt/zaman örneklerinden kWh, ortalama/tepe güç ve maliyet hesaplanır. Sensör veri toplama/enerji dashboardu yok. |
| 165 | Doğrudan MQTT istemcisi | Kurulum/canlı test gerekli | MQTT QoS1 yayın ve tek mesaj okuma istemcisi eklendi; broker/adres/yetki ve canlı broker testi gerekir. |
| 188 | Telefonun bütün bildirimleri | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 189 | SMS okuma/gönderme | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 190 | Telefon arama entegrasyonu | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 202 | Gelişmiş ses temizleme stüdyosu | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 212 | Genel sembolik denklem motoru | Kısmi | SymPy ile sınırlı, güvenli ayrıştırılan denklem/sistem çözümü var. Genel matematiğin tamamı kapsanmaz. |
| 213 | Genel matematik optimizasyon motoru | Kısmi | SciPy HiGHS doğrusal optimizasyonu var; genel doğrusal olmayan/global optimizasyon yok. |
| 214 | Mühendislik hesaplarını bağımsız doğrulama | Kısmi | Sayısal yerine koyma ve denklem kalanı kontrolü var; bağımsız mühendislik modeli/standart doğrulaması değil. |
| 234 | Eksiksiz açık/koyu tema | Kısmi | Ana arayüz ve ayar panellerinde açık/koyu/sistem teması var; bütün 3D/AR modları kapsamlı görsel doğrulamadan geçmedi. |
| 249 | Kapsamlı cevap uzunluğu profilleri | Kısmi | Kalıcı kısa/normal/ayrıntılı tercih ve arayüz seçimi eklendi; bağlama özgü kapsamlı profiller yok. |
| 250 | Bulut/yerel hafıza senkronizasyon seçimi | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 260 | GitHub depo değişikliklerini sürekli izleme | Kısmi | Herkese açık depolar için commit kontrolü ve uygulama açıkken periyodik görev var; özel depo/webhook tabanlı izleme yok. |
| 261 | Tekrarlanan işlerden otomatik makro önerme | Kısmi | Tekrarlanan güvenli iki adımlı eylemlerden isteğe bağlı makro öneri aracı var; proaktif öğrenme sistemi değil. |
| 271 | Bütün API anahtarlarını şifreli kasada saklama | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 272 | Uygulama bazlı internet güvenlik duvarı | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 273 | Güncelleme imza doğrulaması | Bekliyor | Güvenilen yayın imzalama anahtarı, imzalı paket üretimi ve güncelleyiciye zorunlu doğrulama hattı kurulmadı. |
| 286 | Ölçülmüş hızlı başlatma | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 287 | Doğrulanmış düşük RAM | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 288 | Yönetilebilir GPU hızlandırma | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 289 | Tam AI cevap önbelleği | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 290 | Bellek sızıntısı tespit sistemi | Kısmi | Gerçek RSS/CPU örnekleri ve isteğe bağlı tracemalloc kaynak raporu var; artış sızıntı kanıtı değildir. |
| 306 | Genel MCP istemci/sunucu | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 307 | Eklenti mağazası | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 308 | Genel webhook yönetimi | Bekliyor | Bu sürümde uygulanmadı; tamamlandı olarak gösterilmez. |
| 309 | Docker ortam yönetimi | Kısmi | Docker container liste/inceleme/log/start/stop/restart var. Docker kurulumu/daemon gerekir; image/build/compose yönetimi yok. |
| 310 | Sanal makine kontrolü | Kısmi | VirtualBox liste/info/start/pause/resume/ACPI kapatma var; kurulu VirtualBox/VM gerekir. Tüm hipervizörler kapsanmaz. |
| 318 | Gerçek drone uçuş kontrolü | Donanım/ortam gerekli | Uygun cihaz/sensör/çalışma ortamı ve fiziksel doğrulama sağlanmadı; uygulanmış sayılmadı. |
| 319 | ROS/ROS2 | Donanım/ortam gerekli | Uygun cihaz/sensör/çalışma ortamı ve fiziksel doğrulama sağlanmadı; uygulanmış sayılmadı. |
| 320 | Fiziksel görev simülasyonu | Donanım/ortam gerekli | Uygun cihaz/sensör/çalışma ortamı ve fiziksel doğrulama sağlanmadı; uygulanmış sayılmadı. |
| 321 | Tam SLAM | Donanım/ortam gerekli | Uygun cihaz/sensör/çalışma ortamı ve fiziksel doğrulama sağlanmadı; uygulanmış sayılmadı. |
| 322 | Dağıtık model çalıştırma | Donanım/ortam gerekli | Uygun cihaz/sensör/çalışma ortamı ve fiziksel doğrulama sağlanmadı; uygulanmış sayılmadı. |
