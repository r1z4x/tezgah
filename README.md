# Tezgah

Tezgah, aynı repoda kullandığın yapay zekâ kodlama asistanlarını — Claude Code,
opencode, Codex, Cursor — tek bir çalışma sözleşmesine bağlar. Normalde her
birinin kendi alışkanlığı var: biri Türkçe cevap verir diğeri İngilizce, biri kod
ararken `grep`'e abanır diğeri grafiği kullanır, biri test etmeden "tamam oldu"
der. Tezgah kurulduğunda bu fark kalkar; hangi asistanı açarsan aç, aynı dilde,
aynı disiplinde ve aynı doğrulukta çalışır.

İşin özü iki parçadan oluşur: ortak kurallar tek bir dosyada durur, her asistan
da bu kuralları kendi anladığı biçime çeviren ince bir adaptöre sahiptir. Yani
kuralı bir kez değiştirdiğinde dört asistan da aynı şeyi görür; aynı metni dört
yere ayrı ayrı yazmak zorunda kalmazsın.

Pratikte tezgah asistanlara şunları yaptırır: cevap Türkçe ve önce sonuç olacak
(kod ve commit İngilizce kalır), gereksiz soyutlama yapmadan işe yarayan en kısa
çözüm yazılacak, "kim çağırıyor / neyi bozar" gibi sorular `grep` yerine kod
grafiğiyle cevaplanacak, kritik bir karardan önce bağımsız modellere danışılacak,
test edilmeden "yaptım" denmeyecek ve commit/PR metnine `Co-Authored-By` ya da
benzeri bir model atıfı eklenmeyecek.

Bunun karşılığında küçük bir maliyet var ve dürüst olmak gerekirse: her oturum
başında yaklaşık 12,5 KB (≈3.100 token) kural metni bağlama eklenir, Claude'da
ayrıca her turda ~1,3 KB hatırlatma gider. Codex engelleme yeteneği sunmadığı
için orada kurallar tavsiye olarak kalır. Kod grafiği için
`codebase-memory-mcp`, dış görüş için OpenRouter anahtarı ayrıca gerekir; ikisi
de yoksa tezgah sessizce yanlış davranmaz, "yok" der. Gecikme ölçüldü: oturum
başlangıcında Python'un kendi tabanına (19 ms) ek yaklaşık 12 ms, her araç
çağrısındaki kapı ise yaklaşık 0,1 ms. Kurulum ~47 ms sürer ve istendiği kadar
tekrarlanabilir; düzenlediği her dosyayı önce `.tezgah-bak` olarak yedekler.

Kazanç en çok "bu fonksiyonu kim çağırıyor?" sorusunda görünüyor. Gerçek bir
repoda ölçtüm: `grep` varsayılan haliyle ilgili klasörü ignore'a takıp hiçbir şey
bulamadı; ignore'ı kapatıp doğru cevabı aradığında 3,95 saniye sürdü ve yine de
tanım ile çağrıyı karıştırdı. Kod grafiği aynı soruyu 16 milisaniyede, sadece
gerçek 8 çağrı yerini göstererek yanıtladı.

Kurulum basit. Repoyu klonla, `--install` ile dört asistanı bağla; eski bir
kurulumun varsa `--adopt` ile onu devral (siler değil, taşır):

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
bin/tezgah-setup --adopt
```

Claude Code kendi eklenti kanalını kullanır:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Kurduktan sonra günlük hayatta yapman gereken bir şey yok; asistan açılınca
kurallar kendiliğinden yüklenir. Aklında tutman gereken üç komut var:
`tezgah-setup` ne kurulu ne eksik olduğunu söyler, `tezgah-status` o repoda
kuralların aktif olup olmadığını gösterir, `/plan-add` ise bir işi plana çevirir.
Tezgah yalnızca tanımlı kök dizinlerde (varsayılan `~/Projects`) çalışır, başka
yerde tamamen sessizdir.

Geliştirirken `bin/tezgah-setup --sync` kurulu Claude kopyasını bu checkout'la
tazeler ve `claude plugin validate .claude-plugin/plugin.json` manifest'i
doğrular; sürüm yükseltirken iki dosyayı (`.claude-plugin/plugin.json` ve
`.claude-plugin/marketplace.json`) birlikte güncellemek gerekir.
`codebase-memory-mcp` sunucusunu sen kurarsın; Orca'nın hook'ları ve dosyaları bu
projeye ait değildir ve dokunulmaz. Lisans olarak kök `LICENSE` tezgah'ın kendi
dosyalarını kapsar, `skills/ponytail` ile `skills/no-ai-slop` ise kendi MIT
koşullarıyla gelir.
