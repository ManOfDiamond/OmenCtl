# OmenCtl - Yenilikler ve Değişiklik Günlüğü (NEWS)

Bu dosya, OmenCtl v1.6.3 sürümü ve yakın zamandaki tüm mimari geliştirmeleri, yeni özellikleri, hata düzeltmelerini ve güvenlik yapılandırmalarını listeler.

---

## [v1.6.3] - 2026-07-05

### 🌟 Yeni Özellikler & Gelişmiş Güç Yönetimi
* **Gelişmiş Güç Yönetimi (Power Tuning) Sayfası:** `PowerPage` bileşeni (`src/gui/pages/power_page.py`) eklendi. Kullanıcıların işlemci voltaj düşürme (Undervolt), TCC (Thermal Velocity Boost) sıcaklık ofseti belirleme ve özel güç limitleri (PL1/PL2) ayarlamalarına olanak tanındı.
* **Donanım Yeteneklerine Dayalı Koşullu Arayüz (Conditional UI):** D-Bus servis katmanındaki `ModelCapabilities` yapısı genişletilerek `supports_undervolt`, `supports_tcc_offset` ve `supports_power_limits` bayrakları ana arayüze aktarıldı. Bu sayede, yalnızca ilgili donanım özelliklerini destekleyen cihazlarda Güç Yönetimi sayfası ve menü kısayolları aktif hâle gelir; desteklemeyen cihazlarda ise sekme gizlenir ve ana menüdeki kart *Desteklenmiyor* olarak işaretlenir.
* **OmenCore İlhâmı ve Atıf:** Windows ekosistemindeki [OmenCore](https://github.com/theantipopau/omencore) projesinin WMI altyapısı incelenerek, Linux tarafında donanıma en hızlı ve en kararlı erişimi sağlayacak mimari konseptler OmenCtl'ye uyarlandı.
* **Kapsamlı Çoklu Dil Desteği (i18n):** Güç yönetimi, undervolt, TCC ve limit ayarlarına dair tüm etiket ve açıklamalar için `src/gui/i18n.py` dosyasına eksiksiz Türkçe ve İngilizce dil tanımları eklendi.

### 🛠️ Otomatik Başlatma & Arka Plan Kararlılığı
* **GTK Arka Plan Yaşam Döngüsü (`self.hold()`):** OmenCtl sistem açılışında `--hidden` argümanı ile sessiz/arka plan modunda başlatıldığında, GTK pencere yöneticisinin uygulamayı sonlandırmasını engelleyen ve tepsi simgesi (tray) ile sorunsuz çalışmasını sağlayan `self.hold()` mekanizması entegre edildi.
* **Erken Açılış (Early Boot) Yarış Durumlarının Çözümü:** `src/omen-tray.py` dosyasına pystray başlatılırken oluşabilecek sistem hazır olmama (race condition) durumlarına karşı otomatik yeniden deneme (retry) döngüsü eklendi.
* **Başlangıç Gecikmesi Yapılandırması:** `setup.sh` dosyası güncellenerek masaüstü otomatik başlatma (`autostart`) kayıtlarına `sleep` gecikmesi ve `X-GNOME-Autostart-Delay` ayarı eklendi. Bu sayede servislerin masaüstü ortamı tam yüklenmeden önce çökmesi tamamen engellendi.

### 🐛 Hata Düzeltmeleri & Fan Kontrol Optimizasyonları
* **Kullanıcı Özel Fan Eğrilerinin Korunması:** `fan_service.py` dosyasında yer alan `_restore_fan_mode` işlevi düzeltildi. Sistem yeniden başlatıldığında kullanıcının belirlediği 'custom' fan eğrisi modunun sıfırlanması sorunu çözüldü.
* **D-Bus Kota Aşımı (Quota Flood) Koruması:** Uzun süreli kullanımlarda ve oyun esnasında yaşanabilen "Fan control unavailable" hatasının D-Bus kuyruğunu doldurması engellendi. Servis bağlantı koptuğunda güvenli durum sorgulama ve hata toleransı iyileştirildi.
* **EC İzolasyonu ve Güvenliği:** Modern OMEN anakartlarında (örn. 8BAB ve üzeri) doğrudan Legacy EC yazmalarından kaçınılarak `ec_controller.py` katmanı standartlaştırıldı.

### 🛡️ Güvenlik Sıkılaştırması (Security Hardening)
* **Systemd Servis İzolasyonu:** Arka plan mikro servislerinin Systemd yapılandırmalarında en yüksek güvenlik ve sıkılaştırma (hardening) standartları korundu.
* **`status=226/NAMESPACE` Hata Önlemi:** Ubuntu 24.04, Zorin OS ve Linux Mint gibi dağıtımlarda çökme yaratan `PrivateTmp`, `PrivateNetwork` gibi uyumsuz izolasyon parametreleri servis dosyalarından titizlikle arındırıldı ve sistem kararlılığı güvence altına alındı.

---

*OmenCtl'yi tercih ettiğiniz ve topluluğa katkı sağladığınız için teşekkür ederiz!*
