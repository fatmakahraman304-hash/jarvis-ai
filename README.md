# J.A.R.V.I.S. Personal AI — 4.7.0

Windows’ta JARVIS ve FRIDAY kişilikleriyle sesli asistan. Mevcut kullanıcı ayarları,
.env, hafıza ve eklentiler güncellemede korunur. Python 3.10–3.13 ve `start.bat`
kurulumu, Chrome uygulama penceresi ve Telegram desteği sürer.

## Yerel 2D/3D mimari tasarım

Önceki harici planlayıcı, oturum/giriş ekranı ve otomasyon kodları kaldırıldı.
MİMARİ bölümünde **SweetHomeJS / Sweet Home 3D tabanlı yerel editör** açılır.
Paket uygulamayla gelir; Node, Java, ayrı hesap veya model kotası gerekmez.
2D plan ve gerçek 3D modeller aynı editörde, elle düzenlenebilir.

JARVIS’in `architecture_*` araçları ekran üzerinde koordinat tahmini yerine gerçek
proje modelini kullanır. Ölçüler metre, açılar derecedir. Duvarlar, oda çokgenleri,
katlar, kapı/pencereler, gerçek 3D mobilyalar, renkler, kotlar, ölçü çizgileri ve
etiketler düzenlenebilir. Katalog sorgusu, model kimlikleri ve boyutları verir.
Ölçülü otomatik ev planı 7–40 m dış boyut, 1–5 yatak odası ve 1–3 banyo için
koridor, salon, ayrı mutfak, açıklıklar ve temel mobilyalar oluşturur. Sığmayan
oda sayıları reddedilir. Yeni proje açıkça istenmedikçe mevcut proje değiştirilip
sıfırlanmaz; ince düzenleme gerçek nesne kimlikleriyle yapılır.

İşlem grubu başarısızsa atomik geri alınır. Son 20 JARVIS işlem grubu geri
alınabilir/tekrarlanabilir; editörün elle düzenleme geçmişi ayrıca bulunur.
SH3D proje yerel olarak otomatik kaydedilir, son 50 sürüm korunur. Yeniden açma,
SH3D indirme, yerel dosya açma; editörde SVG/PDF/CSV/print ve fotoğraf/görünüm
araçları bulunur. Alan gerçek oda geometrisinden gelir. Ayak izi çakışmaları
uyarıdır; döndürülmüş veya kasıtlı iç içe mobilyalarda uzman çakışma analizi yerine
geçmez. Mimari editör, mühendis imzalı statik/tesisat projesi veya fotogerçekçi
profesyonel render garantisi sunmaz.

3D çözünürlük oranı 1.5 ile, boyama döngüsü yaklaşık 30 FPS ile sınırlıdır;
görünmeyen editörün ağır çizimi durur. Donanıma ve proje boyutuna göre performans
değişir. MİMARİ görünümünde mikrofon ve sohbet açık kalır.

Örnek: “JARVIS, 10 metreye 12 metre, iki yatak odası, ayrı mutfak, salon ve bir
banyolu ev tasarla; kapı, pencere ve temel mobilyaları yerleştir.” Ardından “Salonun
zeminini ahşap tonuna çevir”, “Üst kat ekle”, “Projeyi kontrol et” denebilir.

## Ekran ve fare

`desktop_inspect` Windows UI Automation ile etkin pencerenin gerçek öğelerini,
rollerini ve sınırlarını okur. Şifre alanları ve alan değerleri okunmaz.
`desktop_target` tek hedefi bulur; `desktop_click_target` işlemden hemen önce tekrar
bulur, etkin pencereyi ve üstünü örten pencereyi kontrol ederek fareyi kullanır.
Belirsiz veya kaybolmuş hedefe tahmini tıklama yapılmaz. Uygulamanın erişilebilirlik
desteği gerekir; canvas/oyun/görüntü içeriği için görsel analiz kullanılır.

Ekran analizi görüntü ve erişilebilirlik bilgisini birlikte değerlendirebilir.
Görsel model kotası doluysa piksel gerektiren arayüz işlemi durur; yerel mimari
model işlemleri ve erişilebilirlik hedeflemesi ayrıca çalışır. Negatif monitör
koordinatları, DPI eşleme, adım sonrası gözlem ve ACİL DUR korunur. Windows kilitli
veya UAC güvenli masaüstündeyken bu özelliklerin çalışacağı garanti edilmez.

Davranış ayarlarında semantik Windows tıklamalarını otomatik yapma seçeneği vardır.
Genel koordinat/fare tam otonom tercihi ayrıdır. Hassas işlemlerin mevcut denetimi
sürer. Genel tarayıcı otomasyonu korunur.

## Konuşma

JARVIS doğal, samimi, kısa ve akıcı Türkçe konuşur; “efendim” kalıbını her cümlede
tekrarlamaz. İnce mizah uygunsa kullanılır; hata veya tehlike anında şaka yapılmaz.
Yapılmamış işe “yaptım”, duraklayan işe “devam ediyorum” demez. JARVIS ve FRIDAY
aynı hafızayı paylaşır; sürekli dinleme ve mevcut ses tercihleri korunur.

## Güncelleme ve doğrulama

Uygulamada KONTROL ET → GÜNCELLE; sonra JARVIS’i yeniden başlat. Mimari paket
SHA-256 ile doğrulanır, yerel dizine çıkarılır ve aynı sunucudan servis edilir.
Kaynak ve lisanslar [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) altında.

Regresyonlar: yerel proje ve sürüm kontrolü, model işlem kuyruğu, semantik hedef
çözümleme, fare sınırları, araç bütçesi, gerçek 2D/3D tarayıcı testi, SH3D tekrar
açma, atomik geri alma, mevcut ses/model/diğer özellik testleri. Test ortamı gerçek
Google anahtarını veya kullanıcının bütün Windows uygulamalarını temsil etmez.

Kamera, Dünya elle döndürme ve AR tek efekt modu birbirinden ayrıdır; 4.6.49 kamera ayrımı korunur.

## Kalıcı proje hafızası ve görev devamı

`project_memory` proje/anahtar altında güncel karar ve ölçüleri tutar; aynı karar
anahtarı değiştiğinde eski değer yenisiyle değiştirilir. İlgili kararlar sohbet
başında yerel olarak bulunur; son 60 kayıttan eski ilgili bilgiler de geri gelir.
`task_journal` hedefi, gerçek araç adımlarını ve son durumu SQLite’a yazar.
“Devam et” oturumdaki son yarım hedefi getirir; ekrana/projeye yeniden bakılır,
eski tıklama otomatik tekrarlanmaz. Ayarlar → Hafıza bölümünde proje kararları ve
görev günlüğü görünür. UI görevleri son gözlemle `task_report` raporu ister;
kalan iş varsa paused, engel varsa blocked olur. Modelin raporu tek başına
kullanıcının bütün niyetinin doğru anlaşıldığını kanıtlamaz.

Proaktif öneriler, yarım görev ve en az üç tekrarlı işlem örüntüsüne dayanır.
JARVIS açıkken 09–22 arasında, en fazla saatte bir yerel bildirim/sesli öneri gelir.
Son konuşmadan sonra üç dakika bekler; aynı öneri yedi gün tekrarlanmaz.
Misafir, sessiz saatler ve acil durdurmada çalışmaz. Davranış ayarından veya
“proaktif önerileri kapat” komutuyla kapatılır. Bu işçi ücretli model çağrısı,
ekran tıklaması veya cihaz komutu başlatmaz. Kullanıcının açıkça tanımladığı
makrolar ve zamanlanmış çok adımlı işler mevcut otomasyon üzerinden yürür.

Ekran ayrıntıları için `screen_region` seçili bölgeyi 2000 piksele kadar ayrıntılı
analiz eder. `screen_find` erişilebilirlikte belirsiz hedef bulursa bunu görüntüden
tahmin ederek aşmaz. Görsel sağlayıcı, işletim sistemi ve uygulama desteği gerekir.
Akıllı evde aynı adlı cihazlar tam kimlikle ayrılır; çevrimdışı cihaza komut
verilmez. Home Assistant servis yanıtından sonra durum tekrar okunur. Hedefe
ulaşılamadıysa `verified=false` bildirilir, cihaz çalıştı iddiası üretilmez.
MQTT broker’ı, Home Assistant cihazları, mikrofon ve canlı model hesabı ayrıca
kullanıcının ortamında bağlı olmalıdır.

Kod projeleri/test çalıştırma, kaynaklı web araştırması, veri araçları, sesli
çok adımlı görevler ve Home Assistant/MQTT bağlantıları korunur. Bu sürüm
filmdeki sınırsız yapay zekâ veya her uygulamayı hatasız kontrol garantisi değildir.

Model araçları büyük katalog ve proje listelerini sayfalar; `pages` alanı toplam, dönen öğe ve devam bilgisini verir. Ham JSON kesilerek hedef kimlikleri kaybedilmez.
