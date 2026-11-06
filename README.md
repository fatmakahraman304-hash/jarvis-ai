# J.A.R.V.I.S. Personal AI

## 4.6.45 — Gemini HTTP 429 ve genel HTTP 400 teşhisi

Kota veya hız sınırıyla HTTP 429 döndüren modeller, soğuma süresinde tekrar seçilmez; bu Google kotasını artırmaz. Gemini, yalnızca genel `Request contains an invalid argument` hatası döndürürse isteğe bağlı `thinkingConfig` kaldırılarak, araçlar ve konuşma geçmişi korunarak en fazla bir kez yeniden denenir. Hata sürüyorsa gerçek HTTP 400 gösterilir; başka modellerin HTTP 429 hatasıyla karıştırılmaz. Yeni regresyon testleri tekrarlı isteği ve hata gösterimini kontrol eder. Kota durumunu Google AI Studio Rate limits bölümünden incele. Gerçek hesapla API testi yapılmamıştır.

## 4.6.44 — Gemini araç şeması HTTP 400 düzeltmesi

Gemini'nin `function_declarations[..].parameters.properties[chart].enum[0]: cannot be empty` hatasına neden olan `create_excel.chart` araç tanımındaki boş enum seçeneği kaldırıldı. Parametre artık isteğe bağlıdır: grafik istenmiyorsa hiç gönderilmez, grafik istenirse `bar`, `line` veya `pie` olur. Google Gemini'ye gönderilen tüm iç içe araç şemalarında boş enum seçenekleri de otomatik olarak temizlenir. Tüm kayıtlı araç bildirimlerini tarayan ve boş seçenekleri reddeden regresyon testi eklendi. Güncellemeden sonra JARVIS'i tamamen yeniden başlat.

## 4.6.43 — Tekrarlayan tarayıcı onaylarını azaltma

JARVIS normal tarayıcı gezinmelerinde ve hassas olmayan metin girişlerinde tekrar tekrar onay istemeden çalışır. Bu davranış **Ayarlar > Davranış > Tarayıcıda sıradan işlemleri onaysız yap** seçeneğiyle kapatılabilir; varsayılan açık gelir. Google ile giriş, izin/koşul kabulü, ödeme, silme, paylaşım/çıktı, hassas form alanları ve form gönderme onay korumasını sürdürür. Google hesabına giriş yine Chrome’da elle yapılmalıdır.

Windows masaüstünde genel tıklama, sürükleme ve yazma için önceki **tam otonom** tercihi ayrı kalır ve varsayılan kapalıdır. Acil durdurma ve elle Chrome kullanımı sırasındaki görüntü/araç kilidi değişmez. Otomatik gezinme yalnızca o anki sayfada gerçekten bulunabilen, riskli olarak sınıflandırılmayan kontrollerle sınırlıdır. Bu heuristikler her web sitesinde kusursuz güvenlik garantisi değildir.

## 4.6.42 — Google girişi ve elle kullanım

Güncellemeden sonra JARVIS’i tamamen kapatıp aç. SPACEPLANNER görünümündeki **Chrome’da elle kullan / giriş yap** düğmesine bas. Ayrı Chrome penceresinde koşulları kendin inceleyip kabul et ve **Continue with Google** ile girişini tamamla. Şifreyi JARVIS sohbetine yazma. Google ek doğrulama isterse Chrome’da kendin tamamla. Hesap oluşturulması ve koşulların kabulü otomatik yapılmaz.

Elle kullanım sırasında JARVIS’in araçları ve model için ekran analizi durur; canlı görüntü aktarılmaz. **JARVIS’e geri ver** düğmesi açık Google giriş penceresi veya doldurulmuş görünür şifre alanı varsa geri dönüşü reddeder. Dönüş aynı SpacePlanner sekmesini kullanır, planı yeniden yüklemez. Ardından **devam et** de. Girişin başarılı olup olmadığını site belirler; gerçek hesapla Google girişi test edilmemiştir.

SpacePlanner artık ayrı JARVIS profiliyle normal, görünür yapılabilen Chrome sürecinde çalışır; JARVIS içindeki görünüm korunur. Kişisel Chrome profiline bağlanılmaz. Yerel kontrol bağlantısı yalnızca loopback üzerinde açılır. Chrome penceresini kapatmak yerine JARVIS’e geri ver düğmesini kullan.

## 4.6.41 — Chrome ve JARVIS içinde SpacePlanner

Windows’ta JARVIS penceresi Chrome uygulama moduyla başlar. SpacePlanner için Chrome kurulu olmalıdır; bulunamazsa Edge’e geçmeden kurulum gerektiğini bildirir. Ayrı otomasyon profili korunur.

SpacePlanner açıldığında gerçek Chrome sekmesi arka planda çalışır; sayfanın canlı görüntüsü JARVIS’in SPACEPLANNER görünümünde yenilenir. Sesle verilen çizim komutları aynı sekmeyi kontrol eder. Görünüm mikrofon ve iletişim alanını kapatmaz. Bu alan canlı izleme içindir; fare/klavye etkileşimini JARVIS araçları yapar. Siteyi engellenen iframe içine gömme veya yerel plan editörü kullanılmaz. Görünümü kapatmak planı kapatmaz; tekrar açmak mevcut sekmeyi korur. Görüntü alma API’si mevcut erişim anahtarı denetimine tabidir, sayfa açmaz ve önbelleğe alınmaz.

## 4.6.40 — Çizim boyunca gerçek araç çağrısı

SpacePlanner çizim görevinde ilk açılışla sınırlı kalmadan her model turunda gerçek araç çağrısı gerekir. Model işi sürdürecekse aracı kullanır; duracaksa task_report ile son ekranda gördüğü sonucu/engeli ve kalan işleri bildirir. Yalnızca başlangıç düğmesine basmak tamamlanmış çizim sayılmaz: finished raporu için başarılı tuval çizimi veya masaüstü sürüklemesi ve işlem sonrası gözlem gerekir. Bu asgari kontrol tüm odaların doğruluğunu tek başına kanıtlamaz; son ekranı model değerlendirir.

Başarılı adım önceki metin yanıtlarının sayacını sıfırlar. Adım/süre sınırı ve acil durdurma korunur. Yerel HTTP model sunucusu ve gerçek Chromium testi açılış → çizim → yeni gözlem → rapor akışını sınar; kullanıcının canlı SpacePlanner hesabı burada doğrulanmaz.

## 4.6.39 — Araçtan sonra devam isteği

Gemini’nin verdiği araç kimliği ve imzalı içerik sonraki isteğe aynen taşınır. Araç turunda model korunur; model değişmesi gerekirse eski imzalar yerine gerçek araç sonuçları metin bağlamına aktarılır. SpacePlanner çizim komutları yalnızca tarayıcı araçlarıyla başlar; ekran/fare veya başka gruplar gerektiğinde açılır.

İletişimde araç satırına tıklayarak sonucu okuyabilirsin. Sağlayıcı isteği reddederse HTTP kodu, model ve gerçek hata ayrıntısı anahtar gizlenerek gösterilir. Testler kimlik/imza doğrulayan yerel model sunucusu ve gerçek Chromium kullanır; kullanıcının API hesabı ve canlı SpacePlanner çizimi bu testlerin kapsamında değildir.

## 4.6.38 — Metin yerine gerçek araç çalıştırma

“SpacePlanner aç” gibi eylem isteyen komutlarda ilk adım gerçek function/tool call gerektirir. Gemini’de ANY modu kullanılır; araç desteklenmezse araçsız yapılmış gibi cevap üretmek yerine başka araç destekli model denenir veya açık hata gösterilir. [spaceplanner_open] gibi metinler hiçbir zaman komut olarak ayrıştırılıp çalıştırılmaz. Bozuk yanıt en fazla iki kez gerçek araç çağrısı için yeniden istenir.

Diyalog alanında görev durumu mikrofon dinlemesinden ayrı gösterilir: işlem sonlandı, tamamlanmadı, kalan adımlar var veya onay bekleniyor. Akış tamamlanmadan kesilirse hata görünür. Çizim görevlerinde süre/adım sınırında kalan iş açıklanır; her ev tasarımının tamamlanacağı garanti edilmez. Gerçek hesap/API anahtarı ve kullanıcı cihazı üzerindeki canlı SpacePlanner çizimi ayrıca denenmelidir.


## 4.6.37 — Ev tasarımı yalnızca SpacePlanner

PLAN / ARAÇLAR sekmesi ve yerel mimari editör, oda/mobilya kataloğu, alan/çakışma/metraj araçları, yerel proje sürümleme ve aktarım kodları kaldırıldı. Ev tasarımı için “SpacePlanner aç” veya “ev tasarımı” de: JARVIS kontrollü SpacePlanner sekmesinde çalışır, engelleri kontrol edip her işlemden sonra yeniden analiz eder.

Ses, model bağlantıları, matematik ve sistem araçları korunur. Tema, cevap uzunluğu ve Vosk model yolu mevcut SES ayarlarında bulunur. Vosk için yerel dil modeli gerekir; diğer sağlayıcıları kullanmak için MODELLER’de “Sadece Gemini” seçimini kapatıp kendi API anahtarlarını ekle.

## 4.6.35 — Gör, işlem yap, yeniden analiz et

Ekran ve tarayıcı görevlerinde her etkileşimden sonra yeni analiz modele verilir. Ekran okuma ve etkileşim sonuçları eski önbellekten getirilmez; modelin aynı turda verdiği ikinci arayüz eylemi, yeni görüntü değerlendirilene kadar çalıştırılmaz. İlk masaüstü eyleminden önce de ekran analizi alınır. Onaylanan işlemden sonra asıl görev sürdürülür.

Tarayıcı gözlem aracı görünür modal/çerez/reklam alanındaki açık Kapat, Atla, Şimdi değil veya Tümünü reddet düğmelerini en fazla üç kez kullanıp yeni görüntüyü analiz eder. Hesap, ödeme ve kaydedilmemiş veri pencereleri otomatik kapatılmaz. Yeni reklam sekmesi çalışma sekmesinin yerini almaz; sekmeler analiz edilerek doğru sekmede devam edilir. Özel iframe/canvas engellerinde masaüstü ekran araçları kullanılabilir. Belirsiz engellerin otomatik çözüleceği garanti edilmez; giriş ve CAPTCHA kullanıcı yardımı gerektirebilir.


## 4.6.34 — Ekran analizi ve fare kontrolü

Ekran görüntüsü alma bağımlılığı Pillow ana kuruluma eklendi. Ekran analizi, OCR, öğe bulma, yumuşak fare hareketi, sol/sağ/orta ve çift tıklama, kaydırma ve tutup sürükleme desteklenir. Çoklu monitörün negatif koordinatları korunur, görüntü sınırı dışındaki model yanıtları reddedilir. Her öğe bulma işlemi kendi ekran ölçeğini kullanır. Sürükleme hatayla kesilse bile fare düğmesi bırakılır; acil durdurma fare hareketini keser. Windows masaüstü açık ve erişilebilir olmalıdır.

Örnekler: “JARVIS, ekrandaki hatayı analiz et”, “fareyi Başlat simgesinin üzerine götür”, “bu pencereyi sağa sürükle”. Tıklama, sürükleme ve yazma mevcut ekran kontrolü onay ayarına uyar. Sürekli dinleme ve SpacePlanner özellikleri korunur.


## 4.6.33 — SpacePlanner çizimi ve sürekli ses

SPACEPLANNER düğmesi ve “ev tasarımı” komutu aynı kontrollü Edge/Chrome sekmesini kullanır. Playwright artık gerekli paketlerle kurulur; Windows’ta Edge veya Chrome kurulu olmalıdır. JARVIS görünür çizim tuvalinde tıklama, sürükleme ve ölçü girişi yapabilir; sonucu görüntü ve ölçü alanlarıyla kontrol eder. Örnek: “JARVIS, SpacePlanner’da 4 metreye 3 metre bir oda çiz ve kapı ekle.” Hesap, çıktı, paylaşım ve ücret gerektiren adımlar ayrıca onay isteyebilir.

SİSTEMİ BAŞLAT’a bir kez basıp mikrofon iznini verdikten sonra JARVIS/FRIDAY uyandırması açık kalır. Tek komut mikrofonu kullanıldıktan, tanıma oturumu bittikten veya geçici bağlantı hatasından sonra sürekli dinleme geri döner. Bu sürüme ilk geçişte ses çıkışı ve uyandırma etkinleştirilir; sonrasında elle kapatma tercihi korunur. JARVIS sayfası açık, bilgisayar uyanık kalmalıdır; tarayıcı/işletim sistemi arka planda mikrofonu durdurabilir.

Resmi çizim akışı: https://spaceplanner.co/docs/getting-started

## 4.6.14 — İki kişilik mod, sürekli dinleme ve sadeleştirilmiş arayüz

- Yalnızca J.A.R.V.I.S. ve F.R.I.D.A.Y. kaldı; kaldırılan kişiliğin ses, model, Telegram, makro ve kayıtlı ayarları temizlenir.
- 3D ŞEHİR simülasyonu, komutu, arayüzü, stilleri ve web/city.js dosyası kaldırıldı. Fizik hesaplayıcı ve diğer 3D görünümler korunur.
- Uyandırma kelimesi varsayılan olarak etkinleşir. Sistem başlatma düğmesine bir kez bastıktan ve mikrofon iznini verdikten sonra tarayıcı sayfası açıkken sürekli dinler; "JARVIS" veya "FRIDAY" deyip komutunu söyle.
- Uyandırma kelimesinden sonra ayrı mikrofon düğmesine basman gerekmez. Tarayıcı ve işletim sistemi mikrofon izni ile sürekli konuşma tanıma desteği gerekir.

Tek beyin, çok model, çok platform. İki kişilik: **JARVIS** (mavi, sakin İngiliz uşak) ve **FRIDAY** (turuncu, enerjik operasyon uzmanı). İkisi de aynı hafızayı ve aynı bilgisayar yetkilerini paylaşır; karakter, ses, renk ve model tercihleri farklıdır.

## 3 adımda çalıştır (Windows 11)

1. **Python 3.10+** kur → https://www.python.org/downloads/ (kurulumda *Add python.exe to PATH* kutusunu işaretle).
2. Bu klasörde **`start.bat`**'a çift tıkla. İlk seferde gerekli paketleri kendisi kurar (1–2 dk), sonra JARVIS ayrı bir pencerede açılır.
3. **SİSTEMİ BAŞLAT**'a bas. Model anahtarı yoksa Ayarlar kendiliğinden açılır: en az bir ücretsiz anahtar yapıştır → **ANAHTARLARI KAYDET**.

Ücretsiz anahtarlar (birini almak yeter, ne kadar çok olursa o kadar dayanıklı):

| Sağlayıcı | Nereden | Not |
|---|---|---|
| Google Gemini | aistudio.google.com/apikey | JARVIS'in varsayılanı |
| Groq | console.groq.com/keys | Çok hızlı, FRIDAY'in varsayılanı |
| OpenRouter | openrouter.ai/keys | `:free` modeller (DeepSeek, Llama, Qwen…) |
| Mistral | console.mistral.ai | ücretsiz deneme katmanı |
| Cerebras | cloud.cerebras.ai | çok hızlı |
| xAI Grok | console.x.ai | İsteğe bağlı sağlayıcı; ücretli kredi gerekebilir |
| Ollama | ollama.com | Yerel, **internetsiz**, anahtar gerekmez: `ollama pull qwen2.5` |

**Tek beyin nasıl çalışır:** Her kişiliğin bir model sırası vardır. Bir model kotaya takılır ya da hata verirse beyin aynı cevap için otomatik sıradakine geçer. Model adları her açılışta sağlayıcıdan otomatik okunur, yani modeller değişse de bozulmaz. Ayarlar → Modeller'den her kişiliğe istediğin modeli atayabilirsin.

## Güncelleme (tek tuş)

Alttaki **⟳ GÜNCELLE** düğmesine bas. Yeni sürüm varsa düğme yeşil yanar ("• YENİ") ve notlarını gösterir; **GÜNCELLE**'ye basınca JARVIS:
1. yeni sürümü indirir ve **önce test eder** (test geçmezse hiçbir şey değişmez),
2. mevcut sürümü yedekler (`data/kod_yedekleri`, son 5),
3. dosyaları aynı klasörde günceller — **hafızan, ayarların, `.env` anahtarların ve kendi eklentilerin korunur**,
4. yeni paket gerekiyorsa kurar ve **kendiliğinden yeniden başlar**; sayfa yeni sürümle açılır.
Bir sorun olursa aynı pencerede **↶ ÖNCEKİ SÜRÜME DÖN**. JARVIS ayrıca birkaç saatte bir yeni sürüm olup olmadığını kendisi kontrol edip haber verir.

## Kullanım

- **Yaz** ya da **mikrofon düğmesine bas** (klavyede **Boşluk**). **Esc** konuşmayı keser.
- **👂 UYANDIRMA** açıkken sürekli dinler: *"JARVIS, hava nasıl?"* veya *"FRIDAY bilgisayarımın durumu"*. İsim söylemek kişiliği de değiştirir. Sadece "JARVIS" ya da "FRIDAY" dersen bip sesinden sonra 10 sn komut bekler. O konuşurken "dur"/"sus" ya da ismini söylersen susar.
- **◉ KÜRE / ☺ YÜZ**: dönen nokta küresi ya da 3D hologram yüz. İkisi de sesle birlikte titreşir, yüzün çenesi konuşurken açılır.
- Konuşma tanıma için **Edge veya Chrome** kullan (start.bat zaten Edge'de açar).

### Neler yapabiliyor (300+ araç)

Beyin konuya göre ilgili araçları kendisi seçer; sen sadece ne istediğini söylersin.

| Alan | Örnek komutlar |
|---|---|
| **Gmail** | "okunmamış maillerimi özetle", "Ahmet'ten gelen son maili oku", "buna 'uygun' diye yanıt yaz", "faturaları Faturalar etiketine taşı", "reklam maillerini arşivle", "şu maili spama at", "ekini indir" |
| **Takvim** | "bugünkü programım ne", "cuma 14:00'e dişçi randevusu ekle", "toplantıyı 16:00'ya al", "yarın boş saatlerim", "Ali'yi de davet et, Meet linki koy" |
| **Bildirimler** | Önemli yeni e-posta ve toplantıdan 10 dk önce sesli uyarı (Telegram'a da gider) |
| **Ekranı görme** | "ekranda ne var", "bu hata ne diyor", "ekrandaki yazıyı oku", "Gönder butonuna tıkla", "şunu yaz ve Enter'a bas", "Chrome penceresini öne getir" |
| **Kamera** | 📷 KAMERA düğmesi: "bu ne", "bu belgeyi oku", "QR kodu oku" |
| **Windows** | parlaklık, Wi-Fi, Bluetooth, yazıcı/yazdırma, USB, diskler, başlangıç programları, kurulu programlar, pano, pencereler, kilitle/uyut/kapat, ses, medya tuşları |
| **Donanım** | CPU/RAM/disk/pil, GPU kullanımı ve sıcaklığı, sıcaklık sensörleri, fan, disk sağlığı, "bilgisayarım neden yavaş" teşhisi |
| **Dosyalar** | bul, oku (PDF/Word/Excel), yaz, taşı, sil, yinelenenleri bul, büyük dosyalar, "İndirilenler'i düzenle", zip/unzip, klasör yedekle, geçici dosya temizliği, klasör değişikliklerini izle |
| **Güvenlik** | Defender ve güvenlik duvarı durumu, Defender taraması, şüpheli işlem ve bağlantı taraması, kritik işlemlerde onay |
| **Office** | Word, Excel (biçimli, toplamlı, grafikli), PowerPoint (koyu tema), PDF oluşturma/birleştirme/ayırma/dönüştürme, grafik çizme, veri analizi, dosya karşılaştırma |
| **Finans** | gram/çeyrek altın, döviz, BIST/ABD hisseleri, kripto, fiyat alarmı, harcama/gelir kaydı, kategori bütçesi ve uyarı, aylık rapor, Excel'e aktarma |
| **Otonom görevler** | "her akşam 22:00'de Belgeler'i yedekle", "her sabah 8:30'da brifing ver", "her 30 dakikada önemli mailleri kontrol et". Sen yokken çalışır, başarısız olursa tekrar dener, rapor verir |
| **Yapılacaklar** | son tarihli işler, gecikenleri hatırlatma, günlük brifing |
| **Medya** | YouTube'da çal, Spotify'da çal, müzik/ses kontrolü, ses kaydını yazıya çevirme, YouTube videosu özeti, film/dosya açma |
| **Mesajlaşma** | WhatsApp ve Telegram masaüstünden mesaj gönderme (onaylı) |
| **Akıllı ev** | Home Assistant üzerinden ışık, priz, klima, TV, perde, kilit, sensörler, senaryolar |
| **Cihazlar** | Arduino/robot (seri port), ESP32/Raspberry Pi (HTTP), 3D yazıcı (OctoPrint) |
| **İnternet** | arama, sayfa okuma, hava durumu, haberler, fiyat araştırma |
| **Hafıza** | "bunu hatırla", "unut", eski konuşmalarda arama, yedekleme ve geri yükleme |
| **Ses kimliği** | Seni ve ailedeki diğer kişileri sesinden tanır, "ses kilidi" açıksa sadece tanıdığı seslere cevap verir, kritik işlemi sesle onaylarken sahibinin sesini ister |
| **Konuşma** | Araya girince susar, "devam et" deyince kaldığı yerden sürdürür; cümlenin duygusuna göre ton (heyecan, üzüntü, ciddiyet) |
| **Şifre kasası** | Windows hesabınla şifreli kasa; şifreler yapay zekâya hiç gitmez. "Netflix şifremi kopyala", "güçlü şifre üret", "şifrem güçlü mü" |
| **Alışkanlıklar** | Ekran süresi ve uygulama kullanımı, çalışma alışkanlıkları, pano geçmişi, Windows bildirimlerini okuma |
| **Oyun** | Steam/Epic kütüphanesi, oyun başlat/kapat, FPS (ortalama ve %1 düşük), oyun sırasında CPU/GPU kaydı ve öneriler |
| **Kendini geliştirme** | Kendi kodunu okur, istediğin yeni yeteneği eklenti olarak yazar, **test eder**, geçerse onayınla etkinleştirir (yeniden başlatmadan); GitHub'dan güncelleme alır, testler geçmezse otomatik geri döner |
| **3D Dünya** | 🌍 DÜNYA modu: gerçek dokulu dönen Dünya, gerçek saate göre gece/gündüz, ülke sınırları, tıklayınca nüfus/yüzölçümü/ekonomi/başkent/hava durumu, şehirler, canlı uçuşlar (OpenSky), son depremler (USGS), deniz ticaret rotaları, konum işaretleme, iki nokta arası mesafe, sokak haritası ve uydu görüntüsü, ülke karşılaştırma/sıralama, tarihsel olay turu. "Japonya'ya git", "depremleri göster", "İstanbul ile Tokyo arası kaç km" |
| **Hologram atölyesi** | 🧊 ATÖLYE modu: sanal masada bina, ev, araba, robot, robot kol, gezgin, roket, köprü, dron tasarımı; JARVIS'e tarif ederek her türlü özel 3D model; parçalara ayırma/birleştirme, döndürme, tel kafes, STL olarak kaydetme (3D yazıcıya hazır), STL/OBJ/GLB modelleri açma, 3D grafik |
| **Bilim laboratuvarı** | 🔬 BİLİM modu: güneş sistemi, galaksi ve kara delik, 118 elementin atom modeli, PubChem'den gerçek 3D molekül yapıları, eğik atış, sarkaç, çarpışma, n-cisim yerçekimi, hava akışı (kaldırma kuvveti), elektrik devresi (Ohm), DNA, insan vücudu |
| **El kontrolü** | ✋ EL: kameradan iki el takibi. NESNE (döndür, yakınlaştır, tut-taşı, tıkla, iki elle büyüt), FARE (gerçek fare, pencere sürükleme, kaydırma, sağ tık), KLAVYE (havada klavye), KOMUT (sol el ses, sağ el parlaklık, pozlarla komut, yumrukla kilitle), ROBOT (robot kolu elle yönet), BAŞ/GÖZ (başla imleç, göz kırparak tıkla, bakışla mod değiştir), kendi hareketlerini öğretme |
| **Canlı kamera** | Nesne ve insan algılama/sayma, hareket yönü, yer değiştiren eşya, ışık seviyesi, vücut iskeleti, izinli kişilerin yüzünü tanıma, sesli anlatım |
| **Kontrol** | ⛔ ACİL DUR (düğme, Ctrl+Shift+X, "acil dur", Telegram /dur), misafir modu (tanınmayan ses otomatik), internet kesilince güvenli mod, dosya işlemlerini geri alma, program kur/kaldır/güncelle (winget), monitörler arası pencere taşıma, pencere düzeni, sanal masaüstü, koyu tema/duvar kağıdı/güç planı, kamera-mikrofon gizlilik denetimi, yeni USB/port/başarısız giriş uyarıları |
| **Ağ** | Ağdaki cihazlar, hız testi, ping ve paket kaybı, internet sorunu teşhisi |
| **Günlük** | Sesli alarm (tekrarlı), notlar, alışveriş listesi, haberler |
| **Proje merkezi** | Kod projesi oluşturma, testleri çalıştırma, GitHub (gh CLI) |
| **AR efektler** | EL > ✨ EFEKT (ya da "el efektlerini aç"): kamera görüntüsünde ✋ ateş, ✋✋ dönen mühür halkaları, 🤏 avuçta parçacık gezegen (Satürn, Dünya, Mars, Jüpiter, Ay, Güneş — taşı, fırlat, iki elle büyüt; "Mars yap"), ✊→✋ patlama, ☝☝ şimşek, ☝ ışık izi; 👍 basılı tut = komut, ✌ = mikrofon, ✊ = sus; yüz kilidi HUD'u. Görüntü bilgisayardan çıkmaz |
| **Uyku / alkış** | "uyu" ya da boşta kalınca uyku modu; iki kez alkışlayınca uyanır ve karşılar |
| **Oda tarama + hologram** | 🔎 TARA ya da "odayı tara": nesneler kutulanır; birine tıkla → hologram olarak öne gelir (döner kaide, sürükle-çevir, tekerlekle yakınlaş) + bilgi kartı (ne, marka, boyut, ipucu, 🛒 nerede satılır, 📍 yerini hatırla, soru sor). Telefon kamerası da kaynak olabilir |
| **Nesne hafızası / bulucu** | "kumandayı nerede bıraktım?" (son taramalardan), "kumandayı bul" (kamerada canlı arar, bulunca söyler) |
| **Belge / QR / renk** | "bu belgeyi tara": yazıyı çıkar, özetle, çevir, soruyu çöz, kaydet · QR/barkod (Wi-Fi şifresi dahil) · tıkla → renk adı ve kodu |
| **AR ekstralar** | ✋ sabit avuç → avucunda saat/hava/etkinlik/sistem HUD'u · ✏ havaya çizim (✌ "ne çizdim?", ✊ sil) · 🛡 Iron Man kask HUD'u |
| **Yeni arayüz** | Sade alt şerit + ⊞ UYGULAMALAR (kategorili hologram başlatıcı) · **Ctrl+K / "/"** komut paleti (her özelliği yazarak bul) · üstte tarih ve mini hava · HUD bildirimleri · diyalogda saat, kopyala, "yazıyor" animasyonu · günün saatine göre öneri çipleri · uyku ekranında büyük saat |
| **Hava paneli** | "Hava durumunu göster": büyük HUD paneli — anlık derece, yüksek/düşük, yağmur, UV, gün doğumu/batımı, 24 saatlik eğri, 7 günlük kartlar (Open-Meteo, ücretsiz) |
| **AR masaüstü** | EL > ✨ EFEKT > 🖥 MASAÜSTÜ ya da "AR masaüstünü aç": avucunu açıp sabit tut → dairesel menü; alttaki dock (Saat, Sistem, Hava, Haberler, İşler, Müzik, Dünya, Kılavuz); paneli çimdikle tut-taşı, iki elle büyüt, ✕ ile kapat. Kask modunda yüzüne Iron Man kaskı oturur |
| **Toplantı asistanı** | 🎙 TOPLANTI ya da "toplantıyı kaydet": canlı döküm; bitince özet, kararlar, yapılacaklar (listene eklenir), Belgeler/JARVIS toplantıları'na .md |
| **Odak modu** | ⏳ ODAK ya da "50 dakika odak modu": hologram halka sayaç, bildirimler susar, sonra mola; "bugün kaç dakika odaklandım" |
| **Aydınlat beni** | 📰 GÜNDEM: güncel haberler sahne sahne, büyük sayılar ve kaynaklarla ekranda; her sahne sesli |
| **Bitki doktoru** | TARA > 🌱 BİTKİ ya da "bitkime bak": tür, sağlık, sorun ve bakım; "7 günde bir sulamayı hatırlat", "monsterayı suladım" |
| **Nesneye not** | "Buzdolabına not bırak: süt al" → odayı tarayınca buzdolabının yanında sarı hologram not çıkar ve okunur |
| **Günlük** | "Günlüğüme yaz: …", "bu hafta nasıldım" (yalnızca bu bilgisayarda) |
| **AR oyunları** | "Taş kağıt makas oynayalım" (5 tur, elini okur) · "balon patlatma" (30 sn, işaret parmağıyla; rekor tutulur) |
| **Vücut** | 🧍 VÜCUT: duruş + ekrana mesafe uyarısı ve 20-20-20 göz molası · squat/şınav/zıplama sayacı (sesli sayar) · ruh hali (mutlu/şaşkın/düşünceli/yorgun) |
| **JARVIS'in gözü** | Eski telefonu kamera yap (Ayarlar > PLATFORMLAR > 'Bu cihazı kamera yap' ya da `?rol=kamera`): canlı izle (sol alttaki ● CAM rozeti / 📹 KAMERALAR), "mutfakta ne var?" deyince JARVIS o kameraya bakar. Hareket telefonda algılanır; "güvenlik modunu aç" → hareket olunca bildirim + Telegram'a fotoğraf. Kareler diske yazılmaz |
| **Kitaplık** | 📖 KİTAPLIK: kitaplar, durum, sayfa, not, alıntı; raf fotoğrafından ekle; "kitaplığımı tara" (kameradan); JARVIS kitap defteri yazar (özet, ana fikirler, temalar, rafından benzerler — tanımadığı kitapta uydurmaz). AR'de ☝ ile sırtı seç, 🤏 ile çek → holografik kitap açılır, ✋ savur = sayfa, 👍 = özeti oku, ✊ = rafa koy. Sesle: "X'i bitirdim", "Y'de 120. sayfadayım", "Z'ye not ekle: …", "raftan kitap öner" |
| **YouTube içinde** | "Fenerbahçe maç özetini aç": en yeni özeti bulur, JARVIS'in içinde oynatır |
| **Kahve falı** | "falıma bak": fincanı kameraya göster, telvedeki şekillerden eğlencesine fal (bilim değil) |
| **Telefon** | Dosya gezgini (indir/yükle), Telegram'dan sesli mesaj ve sesli cevap, `/panel` düğmeli uzaktan kumanda (kilitle, uyut — onaylı, ekran, durum, ses, brifing, acil dur), `/ekran` ekran görüntüsü, dosya alma/gönderme, kamera fotoğrafı (izinliyse) |
| **Uzman ajanlar** | Büyük işi parçalara bölüp aynı anda birden fazla ajana yaptırır |
| **Anlamsal hafıza** | Kelimesi kelimesine değil anlamına göre hatırlar ("geçen ay tatil hakkında ne konuşmuştuk"); son hatalarından ders çıkarır |
| **Uzay merkezi** | 🚀 UZAY: gerçek yörünge elemanlarıyla güneş sistemi (tarih ileri/geri), canlı uydular (ISS, Starlink… CelesTrak), "ISS şu an nerede", bu geceki gökyüzü, Ay evresi, Mars, NASA uzay araçlarının konumları (JPL Horizons), kara delik, galaksi, evren |
| **Dünyayı izleme** | Küre katmanları: doğal olaylar (NASA EONET), uydudan yangınlar (FIRMS), günlük uydu fotoğrafı (NASA GIBS), yağmur radarı, 24 ülkenin haber manşetleri haritada, canlı gemiler (AIS) |
| **Yapay zekâ ekibi** | "Ekip kur: …" → yönetici planlar; araştırmacı, kodcu, güvenlik, analist, yazar… uzmanlar bağımlılık sırasıyla paralel çalışır, denetçi kontrol eder, eksikler yeniden yapılır, rapor gelir. Komuta merkezinde canlı izlenir |
| **Çeviri merkezi** | 🌐 ÇEVİRMEN: 22 dil, konuşulan dili otomatik tanır, iki kişi arasında canlı sesli tercüman (her dil kendi sesiyle), görüntülü görüşmede bilgisayar sesini çevirme, kameradaki yazıyı çevirme, videoya SRT altyazı, aynı anda birçok dile çeviri |
| **Görsel stüdyo** | "uzayda bir kedi çiz" (ücretsiz yapay zekâ resmi), fotoğraf düzenleme (kırp, filtre, yazı, filigran, arka plan silme), kolaj, vektör logo (SVG), video: sahne bulma, içerik analizi (kareler + konuşma), kesme, hızlandırma, GIF, birleştirme, altyazı gömme, müzik ekleme, resimlerden montaj |
| **Komuta merkezi** | ⌘ KOMUTA (Ctrl+Shift+K): sistem, güvenlik, ekip, görevler, bağlantılar, bilgisayarlar, modüller tek ekranda. Çalışma modları: sessiz, araştırma, mühendislik, komuta, acil durum. Makrolar: "film modu" deyince bir dizi işi birden yapar. Modülleri aç/kapat |

| **Bilgi merkezi** | 📚 BİLGİ: PDF/Word/EPUB/web sayfası kütüphanesi, kaynak ve sayfa göstererek cevap, özet, 3D bilgi grafiği, sesli kitap (mp3), quiz ve aralıklı tekrar kartları, haftalık öğrenme planı |
| **Bilgisayarlarım** | Ağdaki diğer JARVIS'leri bul/bağla, canlı durumları, uzaktan komut (karşı tarafın izniyle), dosya gönder/al, kapalıysa iş kuyruğu, şifreli bağlantı |
| **Dijital ikiz** | 🖥 İKİZ: bilgisayarının canlı 3D ikizi (çekirdek yükleri, RAM, disk, ağ, GPU, fanlar), Home Assistant'tan evin 3D ikizi (tıkla aç/kapat) |
| **Biyoloji** | 🧬 BİYO: RCSB PDB'den gerçek protein yapıları (hemoglobin, insülin, spike…), hayvan/bitki/bakteri hücresi organelleriyle |
| **Finans laboratuvarı** | 📈 FİNANS: canlı portföy (TL'ye çevrili kâr/zarar), strateji geri testi (SMA, RSI, al-tut), risk ölçüleri (oynaklık, düşüş, Sharpe, beta), Monte Carlo emeklilik/hedef olasılığı, kredi ve bileşik faiz |
| **Müzik** | 🎵 MÜZİK: lofi, sinematik, elektronik, piyano, ambient, hiphop, caz, rock besteler; çalar, WAV ve MIDI indirir; sadece ritim de üretir |
| **Ortam sesleri** | 👂 ORTAM: duman/yangın alarmı, cam kırılması, çığlık, bebek ağlaması, kapı zili/çalınması, köpek havlaması… algılar, uyarır, Telegram'a bildirir |
| **Tarayıcı otomasyonu** | JARVIS kendi Edge/Chrome penceresinde siteye gider, sayfayı okur, numaralı öğelere tıklar, form doldurur, sekmeleri yönetir ("uçak bileti sitesinde İstanbul–Ankara cuma ara"). Şifre alanına yazmaz; satın al/öde/gönder/sil gibi düğmeler her zaman onay ister |
| **Yayın / kayıt** | OBS Studio: "kaydı başlat", "yayını durdur", "sahneyi Sohbet yap", "son 30 saniyeyi kaydet" (OBS WebSocket) |
| **Fatura** | "Ali Veli'ye 10 saat danışmanlık 1.250 TL'den fatura kes" → KDV'li PDF fatura/proforma |
| **VR / AR** | Her 3D dünya VR gözlükte (Quest/Pico tarayıcısı, SteamVR/WMR) ya da ARCore'lu telefonda AR olarak açılır; kumanda tetiğiyle seçim (`start-vr.bat`) |

**Gmail'i bağlamak (bir kez, ~5 dk):** Ayarlar → BAĞLANTILAR'da adım adım yazıyor: Google Cloud'da proje aç, Gmail ve Calendar API'yi etkinleştir, kendini test kullanıcısı yap, "Masaüstü uygulaması" istemcisi oluştur, Client ID/Secret'ı yapıştır, **GOOGLE'A BAĞLAN**. Bağlantı yetkisi sadece senin bilgisayarında (`data/google_token.json`) durur.

### Güvenlik

- **Kritik işlemler onaysız yapılmaz:** e-posta gönderme/yanıtlama, e-postayı çöpe atma, davetli etkinlik, silme, taşıma, var olan dosyanın üzerine yazma, program kapatma, bilgisayarı kapatma, komut çalıştırma, WhatsApp/Telegram mesajı, ekranda tıklama/yazma (Ayarlar'dan kapatılabilir), kilit açma. Ekranda turuncu **ONAYLA / REDDET** kartı çıkar.
- Silinen dosyalar kalıcı silinmez: geri dönüşüm kutusuna (ya da `data/cop_kutusu`) gider.
- Sunucu varsayılan olarak **sadece bu bilgisayara** açıktır. Telefon modu erişim anahtarı ister; API anahtarları uzaktan değiştirilemez.
- Anahtarlar `.env` dosyasında, hafıza `data/` klasöründe durur; ikisi de `.gitignore`'da, GitHub'a gitmez.


## Hızlı konuşma ve akıllı bağlam (v4.6.5)

Mark-LVI'den ilham alan iki sohbet iyileştirmesi:

- **4.6.6 hata düzeltmesi:** Hızlı sesli karşılık hazırlanırken eksik `re` modülü içe aktarımı eklendi; `chromu aç` gibi araç komutlarında görülen `NameError` giderildi.
- **Anında karşılık:** İnternet, dosya, bilgisayar veya üretim araçları gerektiren web/telefon isteklerinde JARVIS, model cevabını beklerken kısa bir sesli durum bildirimi verir. Basit sohbetlerde gereksiz konuşma eklenmez; bu bildirim ayrı tutulur ve asıl cevabın içine karışmaz.
- **Bütçeli konuşma bağlamı:** Model isteğine en yeni konuşma mesajları en fazla 24.000 karakterlik kayan pencereyle eklenir. Eski mesajlar SQLite geçmişinden silinmez; yalnızca hız ve bağlam boyutu için o isteğin dışında bırakılır.
- Mevcut çoklu model yönlendirmesi, araç çağrıları, kritik işlem onayları ve kalıcı hafıza aynen korunur.
- `tests/test_fast_conversation.py` bu davranışlar için regresyon kapsamı sağlar; yeni güncelleyici bu testi sonraki sürüm yükseltmelerinde ön kontrolde çalıştırır.

Yeni sürüm, Ayarlar > **GÜNCELLE** üzerinden version.json sürümü görüldüğünde kurulabilir.


## Model dağılımı ve hız (v4.6.11)

JARVIS, Mark LVI'nin görev bazlı model sıralamasını mevcut tarayıcı konuşma hattına uyarlar:

- **FAST:** kısa komutlar — Gemini 3.5 Flash-Lite → 3.1 Flash-Lite → 3.8 Flash → 3.6 Flash → 3.5 Flash.
- **SMART:** uzun/karmaşık işler, planlama, kod ve görüntü muhakemesi — Gemini 3.8 Flash → 3.7 Flash → 3.6 Flash → 3.5 Flash → Flash-Lite yedekleri.
- **SEARCH:** arama aracı seçimi ve kaynaklı araştırma — Gemini 3.5 Flash-Lite → 3.1 Flash-Lite → 3.8 Flash → 3.6 Flash → 3.5 Flash.

FAST ve SEARCH isteklerinde 10 saniye, SMART isteklerinde 20 saniye model sınırı kullanılır. 503/504 alan model 30 dakika dinlendirilir ve aynı istekte yeniden denenmez.

### Hızlı araştırma akışı (4.6.11)

- Bing, DuckDuckGo ve DuckDuckGo Lite paralel aranır; ilk işe yarar sonuçta dönülür.
- Google Haberler yalnızca haber/güncel sorgularında eklenir. Google Grounding normal web sonuçları bulunamadığında yedek olarak çağrılır.
- Bir sohbet turunda başarılı web aramasından sonra yeni web_search/news_search araçları modelden kaldırılır. Sonuç için gerçekten gerekliyse en fazla bir read_webpage çağrısı yapılır.
- Araştırma model turu dört adımla sınırlıdır; normal görevlerin adım bütçesi korunur.

**Ses motoru notu:** Mark LVI'nin ana konuşması Gemini 3.1 Flash Live ile çift yönlü ses oturumu kullanır. Bu JARVIS arayüzü hâlâ tarayıcı konuşma tanıma + Edge TTS kullanır; ancak metin akışı cümlelere bölünerek cevap tamamlanmadan ses kuyruğuna verilir. Live ses oturumu henüz web konuşma hattına taşınmadı.

## Gemini 2.5 erişim kısıtları (4.6.8)

Google, Gemini 2.5 modellerini yeni API projelerinde kısıtladığından JARVIS bu modelleri varsayılan/yedek sıralarından çıkarmıştır. Eski `GEMINI_MODEL`, `GEMINI_VISION_MODEL` ve kişilik model sabitlemelerindeki 2.5 değerleri açılış geçişinde temizlenir. Erişim hatası (404) alan model altı saat dinlendirilir.

Güncel FAST / SMART / SEARCH modeli sırası için yukarıdaki **Model dağılımı ve hız (v4.6.11)** bölümüne bak.

Kaynak: Google Gemini API model kataloğu: https://ai.google.dev/gemini-api/docs/models

## Windows 4.6.9 bağlantı kapanışı

Windows Python Proactor event loop, tarayıcı/istemci bağlantıyı aniden kapattığında `ConnectionResetError: [WinError 10054]` mesajını bazen callback hatası olarak yazdırabilir. JARVIS 4.6.9 yalnızca `_ProactorBasePipeTransport._call_connection_lost` sırasında gelen bu belirli reseti sessiz ele alır; diğer asyncio hataları normal şekilde gösterilir. Varsayılan Proactor event loop korunur.

**`Invalid HTTP request received`** farklı bir uyarıdır: sunucuya geçersiz HTTP veya yanlış protokolle gelen bağlantı isteğini gösterir. Normal bilgisayar modunda ekranda yazan `http://127.0.0.1:8765`, LAN/HTTPS modunda ekranda yazan `https://...` adresini kullan. Yanlış protokol isteği devam ediyorsa tarayıcı adresini, uzantıları veya güvenlik yazılımının yerel port taramasını kontrol et.


## Güncelleme testi düzeltmesi (v4.6.10)

4.6.9 model yönlendiricisi 503/504 alan bir modeli aynı istekte tekrar denemeden bir sonraki modele geçirir ve 30 dakika dinlendirir. `tests/test_models.py` içindeki eski beklenti aynı modeli tekrar denemeyi ve 2 dakikalık beklemeyi beklediği için güncelleme ön kontrolünü yanlışlıkla başarısız yapabiliyordu. Test artık uygulamanın gerçek no-retry / 30 dakika cooldown davranışını doğrular.

## Çok platform

| Nereden | Nasıl |
|---|---|
| Bilgisayar | `start.bat` |
| Telefon (aynı Wi-Fi) | `start-lan.bat` → pencerede yazan `https://192.168…/?token=…` adresini telefonda aç → ilk sertifika uyarısında **Gelişmiş > Devam et** → tarayıcı menüsünden **Ana ekrana ekle**. HTTPS kamera/mikrofonu da destekler. |
| VR gözlük | `start-vr.bat` → gözlüğün tarayıcısında pencerede yazan `https://…` adresini aç ("Gelişmiş > Devam et") → bir 3D dünya seç → 🥽 VR |
| Diğer bilgisayarlar | Her birinde `start-lan.bat`; birinde ⌘ KOMUTA → BİLGİSAYARLARIM → AĞI TARA → anahtarı gir → BAĞLA. Uzaktan komut için diğerinde Ayarlar → Bağlantılar → "Ağdaki diğer JARVIS bilgisayarlarından gelen komutlara izin ver" |
| Telegram (her yerden) | @BotFather → `/newbot` → token'ı `.env`'de `TELEGRAM_BOT_TOKEN`'a yaz, JARVIS'i başlat, bota yaz; bot sana kullanıcı kimliğini söyler → `TELEGRAM_ALLOWED_IDS`'e yaz, yeniden başlat. Komutlar: `/panel` `/ekran` `/kilitle` `/durum` `/brifing` `/ses` `/jarvis` `/friday` `/onay KOD` `/iptal KOD` `/dur` (telefondaki `/` menüsünde de listelenir). Bot senin bilgisayarında çalışan beyne bağlıdır; bilgisayar açık olmalı. |

## Sesler hakkında

Sesler ücretsiz Microsoft Neural seslerinden (edge-tts, anahtar gerekmez) ayarlanır ve tarayıcıda kişiliğe özel efekt eklenir: JARVIS'e hafif yankı ve netlik, FRIDAY'e sıcak hafif yankı. Ses dili Otomatik/Türkçe/İngilizce seçilebilir; İngilizce'de JARVIS İngiliz (Ryan), FRIDAY İrlandalı (Emily) aksanıyla konuşur. Filmdeki oyuncuların seslerinin kopyası **değildir** (gerçek kişilerin sesini izinsiz klonlamak doğru olmaz); film havasına yaklaştıran ayarlardır. Hız/ton sürgüleri Ayarlar → Ses'te.

### Kullanıcıya ait orijinal ses klipleri (Türkçe + İngilizce)

İzinli/sahibi olduğun film ses kayıtlarını kullanmak için:
1. `data/voice_assets/` klasörünü oluştur.
2. `voice_assets/manifest.example.json` dosyasını örnek alarak `data/voice_assets/manifest.json` oluştur.
3. Ses dosyalarını `data/voice_assets/` altına koy. Manifestte her karakter ve dil için **tam cümleyi** anahtar, göreli dosya yolunu değer olarak yaz. Örnek: `"sistemler çevrimiçi, efendim.": "jarvis/tr/greeting.mp3"`.
4. Karakterin konuşacağı cümle manifestte birebir (büyük/küçük harf ve boşluk farkları yok sayılır) eşleşirse kayıt çalınır. Eşleşme yoksa mevcut Microsoft Neural TTS otomatik kullanılır.

Desteklenen biçimler: MP3, WAV, OGG, M4A ve WebM. Dosyalar yerel `data/` klasöründe kalır; Git'e eklenmez. Bu yöntem kayıtlı replikler içindir; film oyuncusunun sesini sınırsız yeni cümleler için klonlamaz.

## Proje yapısı

```
run.py               başlatıcı (--lan telefon/ağ, --https şifreli, --port, --no-browser)
core/brain.py        TEK BEYİN: ajan döngüsü, araç çağrısı, onay sistemi
core/llm.py          çoklu model yönlendirici (Gemini, Groq, OpenRouter, Grok, Mistral, Cerebras, Ollama)
core/personas.py     JARVIS / FRIDAY karakter, ses, renk
core/tools.py        temel araçlar + akıllı araç seçimi
core/skills/         31 yetenek modülü: google, computer, windows, office, finance(+lab), automation, smarthome, media,
                     geo, holo, space, worldwatch, team, translate, studio, command, world, knowledge, nodes, twin, music…
plugins/             kendi eklentilerin (örnek: ornek_eklenti.py)
core/memory.py       SQLite kalıcı hafıza
core/voice.py        ses üretimi
core/telegram_bot.py Telegram köprüsü
core/server.py       web API + güvenlik
web/                 arayüz (Three.js gömülü, internetsiz de açılır)
tests/               python tests/test_smoke.py · test_skills.py · test_more.py · test_nodes.py (+ node tests/test_ui.js)
```

**Yeni yetenek eklemek:** `plugins/` klasörüne bir `.py` dosyası koy (örnek: `ornek_eklenti.py`), JARVIS'i yeniden başlat. Beyin onu otomatik kullanmaya başlar.

## Sorun giderme

- *"Henüz hiçbir model bağlı değil"* → Ayarlar → Modeller'e anahtar gir.
- Ses çıkmıyor → Ayarlar → Ses'teki nota bak; edge-tts yoksa tarayıcı sesi kullanılır (`.venv\Scripts\pip install edge-tts`).
- Mikrofon çalışmıyor → Edge/Chrome kullan, adres çubuğundaki mikrofon iznini ver.
- Telefon bağlanmıyor → Windows Güvenlik Duvarı ilk açılışta soracak, "Özel ağ"a izin ver. `start-lan.bat` artık otomatik HTTPS açar; telefonda ekranda yazan `https://` adresini kullan.
- Video araçları "ffmpeg bulunamadı" diyor → bir kez `winget install Gyan.FFmpeg` (ya da JARVIS'e "ffmpeg kur" de), JARVIS'i yeniden başlat.
- El/kamera algılama, ortam sesi tanıma ilk açılışta internetten model indirir (MediaPipe); sonra tarayıcı önbellekten kullanır.
- Resim üretimi yanıt vermiyor → Pollinations yoğun olabilir; `.env`'e ücretsiz `HF_TOKEN` ekle (yedek olarak FLUX kullanılır).
- VR düğmesi görünmüyor → adres `https://` olmalı (`start-vr.bat`) ve tarayıcı WebXR desteklemeli.
- iPhone kamera açılmıyor → `start-lan.bat` ile JARVIS'i yeniden başlat, konsoldaki yeni `https://` adresini aç ve Safari'de kamera izni ver. `http://172…` gibi IP adresli HTTP bağlantıları kamera API'sini engeller.
