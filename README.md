# Tezgah

Tezgah, aynı repoda kullandığın yapay zekâ kodlama asistanlarını — Claude Code,
opencode, Codex, Cursor ve DeepSeek'in dsh harness'ı — tek bir çalışma
sözleşmesine bağlar. Normalde her birinin kendi alışkanlığı var: biri Türkçe
cevap verir diğeri İngilizce, biri kod ararken `grep`'e abanır diğeri grafiği
kullanır, biri test etmeden "tamam oldu" der. Tezgah kurulduğunda bu fark
kalkar; hangi asistanı açarsan aç, aynı dilde, aynı disiplinde ve aynı doğrulukta
çalışır.

İşin özü iki parçadan oluşur: ortak kurallar tek bir dosyada durur, her asistan
da bu kuralları kendi anladığı biçime çeviren ince bir adaptöre sahiptir. Yani
kuralı bir kez değiştirdiğinde beş asistan da aynı şeyi görür; aynı metni beş
yere ayrı ayrı yazmak zorunda kalmazsın.

Pratikte tezgah asistanlara şunları yaptırır: cevap Türkçe ve önce sonuç olacak
(kod ve commit İngilizce kalır), gereksiz soyutlama yapmadan işe yarayan en kısa
çözüm yazılacak, "kim çağırıyor / neyi bozar" gibi sorular `grep` yerine kod
grafiğiyle cevaplanacak, kritik bir karardan önce bağımsız modellere danışılacak,
test edilmeden "yaptım" denmeyecek ve kalıcı ya da yayınlanan hiçbir metne —
commit/merge/tag mesajına, PR/issue/review yazısına, dosya başlığına, yorum ya da
dokümana — AI/model atıfı eklenmeyecek: ne `Co-Authored-By`, ne "Generated with",
ne robot emoji, ne de Claude/Anthropic/OpenAI/Codex/Gemini/Cursor/Copilot adı.
Bir aracı kullanmak için anmak serbest; onu yazar olarak yazmak yasak.

Bunun karşılığında küçük bir maliyet var ve dürüst olmak gerekirse: her oturum
başında yaklaşık 12,5 KB (≈3.100 token) kural metni bağlama eklenir, Claude'da
ayrıca her turda ~1,3 KB hatırlatma gider. Codex artık tezgah'ın engelleme
kapısını da bağlar: `PreToolUse` kaydı Bash, `exec_command`, `apply_patch`,
Edit/Write, MCP araçları ve alt-ajan çağrılarını aynı denetimden geçirir, yani
orada da kurallar tavsiye olarak değil kapı olarak durur. Atıf yasağı Claude'da
yalnızca hook denetimine bırakılmaz; `attribution` ayarı `commit`, `pr` ve
`sessionUrl` boşaltılarak commit/PR atıfı kaynağında kapatılır. dsh'te ise
Claude hook köprüsü kullanıldığı için sözleşme ve
kapı aynen çalışır. Kod grafiği için `codebase-memory-mcp`, dış görüş için
OpenRouter anahtarı ayrıca gerekir; ikisi de yoksa tezgah sessizce yanlış
davranmaz, "yok" der. Gecikme ölçüldü: oturum başlangıcında Python'un kendi
tabanına (19 ms) ek yaklaşık 12 ms, her araç çağrısındaki kapı ise yaklaşık
0,1 ms. Kurulum ~47 ms sürer ve istendiği kadar tekrarlanabilir; düzenlediği her
dosyayı önce `.tezgah-bak` olarak yedekler.

Kazanç en çok "bu fonksiyonu kim çağırıyor?" sorusunda görünüyor. Gerçek bir
repoda ölçtüm: `grep` varsayılan haliyle ilgili klasörü ignore'a takıp hiçbir şey
bulamadı; ignore'ı kapatıp doğru cevabı aradığında 3,95 saniye sürdü ve yine de
tanım ile çağrıyı karıştırdı. Kod grafiği aynı soruyu 16 milisaniyede, sadece
gerçek 8 çağrı yerini göstererek yanıtladı.

Kurulum basit. Repoyu klonla, `--install` ile algılanan tüm asistanları (Claude,
opencode, Codex, Cursor, dsh) bağla; eski bir kurulumun varsa `--adopt` ile onu
devral (siler değil, taşır):

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

Plugin yalnızca hook ve komut getirmez; iki salt-okunur ajan da taşır.
`agents/tezgah-explorer.md` kod keşfini grafikten yapıp `file:line` kanıtıyla
döner, `agents/tezgah-reviewer.md` ise bir diff'i önce `detect_changes` ile
etki alanına çevirip sonra çekişmeli bir incelemeyle gerçek kusurları arar;
ikisinin de yazma ve komut araçları kapalıdır, çıktıları öneridir.

Kurduktan sonra günlük hayatta yapman gereken bir şey yok; asistan açılınca
kurallar kendiliğinden yüklenir. Aklında tutman gereken üç komut var:
`tezgah-setup` ne kurulu ne eksik olduğunu söyler, `tezgah-status` o repoda
kuralların aktif olup olmadığını gösterir, `/plan-add` ise bir işi plana çevirir.
Sürümü `bin/tezgah-setup --version` ile okursun; kurulumu geri almak istersen
`bin/tezgah-setup --uninstall` yalnızca tezgah'ın bağladığı symlink'leri, host
hook kayıtlarını ve dsh'teki yönetilen bloğu söker, başka bir dosyaya ya da
`.tezgah-bak` yedeğine dokunmaz. Tezgah yalnızca tanımlı kök dizinlerde
(varsayılan `~/Projects`) çalışır, başka yerde tamamen sessizdir.

Durum satırı her host'ta aynı değil ve bunu gizlemiyoruz: Claude Code ile Cursor
CLI'da (`~/.cursor/cli-config.json`, spec'i Claude'la hizalı) tezgah segmenti
otomatik bağlanır; opencode'da komut tabanlı statusLine olmadığı için segment
ancak bir **TUI plugin'i** ile görünür ve bu plugin kurulur; Codex'in TUI footer'ı
kapalı bir yerleşik öğe listesi olduğundan footer'a segment eklenemez, bu yüzden
orada segment oturum başında ve her tur sonunda hook `systemMessage` ile görünür.
dsh'te de komut statusline yok; native bir UI plugin'i ile sidebar'a eklenebilir
ama bu ağır bir iştir ve henüz paketlenmedi.

Geliştirirken `bin/tezgah-setup --sync` kurulu Claude kopyasını bu checkout'la
tazeler ve `claude plugin validate .claude-plugin/plugin.json` manifest'i
doğrular; sürüm yükseltirken iki dosyayı (`.claude-plugin/plugin.json` ve
`.claude-plugin/marketplace.json`) birlikte güncellemek gerekir.
`codebase-memory-mcp` sunucusunu sen kurarsın; Orca'nın hook'ları ve dosyaları bu
projeye ait değildir ve dokunulmaz. Lisans olarak kök `LICENSE` tezgah'ın kendi
dosyalarını kapsar, `skills/ponytail` ile `skills/no-ai-slop` ise kendi MIT
koşullarıyla gelir.
