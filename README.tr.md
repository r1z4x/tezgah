<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.zht.md">繁體中文</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.da.md">Dansk</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.bs.md">Bosanski</a> |
  <a href="README.no.md">Norsk</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.th.md">ไทย</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.uk.md">Українська</a> |
  <a href="README.bn.md">বাংলা</a>
</p>

# Tezgah

<p align="center">
  <img src="assets/logo/tezgah-logo.svg" alt="tezgah logo" width="220">
</p>

<h3 align="center">Çalıştırdığınız her yapay zeka kodlama asistanı için tek bir çalışma sözleşmesi.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Neleri zorunlu kılar</a> &bull;
  <a href="#supported-hosts">Desteklenen barındırıcılar</a> &bull;
  <a href="#install">Kurulum</a> &bull;
  <a href="#day-to-day">Günlük kullanım</a> &bull;
  <a href="#configuration">Yapılandırma</a> &bull;
  <a href="#cost">Maliyet</a> &bull;
  <a href="#development">Geliştirme</a> &bull;
  <a href="#contributing">Katkıda bulunma</a> &bull;
  <a href="#security">Güvenlik</a> &bull;
  <a href="#license">Lisans</a>
</p>

<p align="center"><sub>İngilizce ana kaynaktır; çeviriler geriden gelebilir.</sub></p>

---

Yapılandırılmış bir dizi depo kök dizini içinde, çalıştırdığınız her yapay zeka kodlama asistanı — Claude Code,
opencode, Codex, Cursor ve DeepSeek'in dsh donanımı — için tek bir çalışma sözleşmesi.

Kendi haline bırakıldığında, her asistanın kendi alışkanlıkları vardır: biri Türkçe cevap verir, diğeri
İngilizce; biri her şey için grep kullanır, diğeri bir kod grafiğini sorgular; biri test çalıştırmadan
"tamamlandı" der. tezgah bu sapmayı ortadan kaldırır. Herhangi bir barındırıcıyı açtığınızda
aynı dili, aynı disiplini ve aynı kanıt standardını elde edersiniz.

Tasarım iki katmanlıdır. Kurallar paylaşılan bir çekirdekte bir kez yer alır; her barındırıcı,
bu çekirdeği barındırıcının anladığı şekle çeviren ince bir adaptör alır.
Bir kuralı tek bir yerde değiştirdiğinizde beş barındırıcının tümü bunu görür — aynı metnin
beş ayrı kopyası yoktur.

<a id="what-it-enforces"></a>

## Neleri zorunlu kılar

- **Sonuç odaklı Türkçe raporlama.** Her yanıt Türkçedir ve sonuç veya kararla (BLUF) başlar,
  ardından etki sırasına göre maddeler gelir. Kod, commit'ler, belgeler ve alt ajan (subagent)
  istemleri İngilizce kalır; isimler, CLI komutları ve hata dizeleri asla çevrilmez.
- **Minimal kod (ponytail).** Gerçekten işe yarayan en tembel değişiklik: YAGNI,
  ardından mevcut bir yardımcıyı yeniden kullanma, ardından stdlib, ardından yerel bir platform özelliği,
  ardından kurulu bir bağımlılık, ardından tek bir satır. İstenmeyen soyutlamalar yoktur.
  Doğrulama, hata yönetimi ve güvenlik asla basitleştirilerek geçiştirilmez.
- **Önce kod grafiği ile keşif.** "X nerede", "Y'yi kim çağırıyor", "Z değişirse ne bozulur"
  gibi sorular grep'e değil, `codebase-memory-mcp` grafiğine (`search_graph`,
  `trace_path`, `search_code`) gider. Grep; düz metinler, yapılandırmalar ve
  kod olmayan dosyalar için doğru seçenek olmaya devam eder.
- **Önce erişilebilirlik ile uygulama analizi.** Çalışan bir web veya mobil uygulama, her adımda
  bir ekran görüntüsü ile değil, erişilebilirlik / DOM / yerel görünüm ağacı üzerinden okunur.
  `analyze-app` bir tarayıcıyı (Playwright MCP), bir iOS Simülatörünü veya Android emülatörünü (Mobile MCP)
  ve isteğe bağlı web tanılamalarını (Chrome DevTools MCP) kapsar; bir ekran görüntüsü,
  ağacın yanıtlayamadığı durumlar için açık, isteğe bağlı bir eylemdir.
- **Harici ikinci görüş.** Önemsiz olmayan veya geri alınması zor bir karardan önce,
  `~/.config/tezgah/bin/consult` OpenRouter (veya `--provider deepseek` ile DeepSeek API)
  aracılığıyla bağımsız modellere paralel olarak danışır ve ajan (agent) bunların nerede
  anlaştığını veya anlaşmazlığa düştüğünü raporlar.
- **OpenResearch aracılığıyla araştırma.** Yönlendirici (router) bir görevin araştırma olduğuna karar verdiğinde —
  literatür taraması, hipotez oluşturma ve test etme, deneyler yürütme, bir araştırma eseri —
  işi alphaXiv'in OpenResearch'ü (`orx`) üzerinden yürütür ve protokolü doğaçlama yapmak yerine
  önce `orx` kılavuzunu yükler. Düz kod keşfi kod grafiğinde kalır. `orx` bulunmadığında,
  yönlendirici bunu belirtir ve bir barındırıcı alt ajanına (subagent) geri döner.
- **Doğrulama altında dürüstlük.** Çıktı görülmediği sürece hiçbir şeyin yapıldığı, test edildiği veya
  düzeltildiği rapor edilmez. Başarısız olan bir test, tam hatasıyla birlikte başarısız olarak
  rapor edilir ve atlanan bir kontrol açıkça belirtilir.
- **Hiçbir yerde yapay zeka atfı yok.** Kalıcı hale getirilen veya yayınlanan hiçbir şey — commit,
  merge ve tag mesajları, PR ve issue metinleri, kod yorumları, dosya başlıkları, belgeler
  — asistana, modele, satıcıya veya "yapay zeka"ya (AI) atıfta bulunamaz. Bir aracı kullanmak sorun değildir;
  ancak onun adını kendi çalışmanıza imzalamak kabul edilemez.
- **İki aşamalı orkestrasyon.** Ana iş parçacığı (main thread) karar verir ve doğrular; ucuz bir
  model (`~/.config/tezgah/bin/codegen`, varsayılan olarak OpenRouter veya `--provider deepseek`)
  geçici bir dizine (scratch directory) sınırları belirlenmiş, iyi tanımlanmış düzenlemeler tasarlar.
  Yönlendirici (router) dışında hiçbir şey depoya ulaşmaz ve başarısız bir taslak otomatik olarak
  ana modele geri döner.
- **Depo başına alt ajanlar (subagents).** Oturum başlangıcında, kapsayan depo, yetenekleri
  sınırlandırılmış küçük bir ajan seti (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) ve bir `tezgah-orchestrator` alır; bunlar
  kurulu her barındırıcının yerel yüzeyine (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` artı canlı bir yapılandırma enjeksiyonu, Codex
  `.codex/agents/`) işlenir ve yönetilen tek bir `.gitignore` bloğu ile yoksayılır. Claude'da
  orkestratörün `Agent(tezgah-*)` izin listesi yalnızca ana iş parçacığı olarak çalıştığında
  (`claude --agent tezgah-orchestrator`) geçerli olur; bir alt ajan olarak liste yoksayılır.
  dsh'nin rol başına bir yüzeyi yoktur, bu nedenle sözleşmenin yönlendirici kuralı onu kapsar.

<a id="supported-hosts"></a>

## Desteklenen barındırıcılar

| Barındırıcı | Bağlantı yöntemi | Durum çubuğu |
|---|---|---|
| **Claude Code** | yerel eklenti pazarı: kancalar (hooks), komutlar, iki salt okunur ajan, çıktı stili | yerel `statusLine` |
| **opencode** | eklenti + talimatlar + MCP + oluşturulmuş yetenek yönlendiricisi (yerel yetenek listesi reddedilir), ilk mesajda depo otomatik indeksleme | TUI eklentisi (komut statusLine'ı yok) |
| **Codex** | `hooks.json` + yetenekler + MCP, bir `PreToolUse` geçidi dahil | kanca (hook) `systemMessage` (altbilgi öğe listesi kapalıdır) |
| **Cursor** | `hooks.json` + yetenekler + MCP | `cli-config.json` içinde `statusLine` |
| **dsh** | Claude Code kanca köprüsü + yönetilen yama bloğu (kancalar, MCP, LLM rotaları, ağaç dışı bir Web durum çubuğu) | Web UI eklentisi: oturum başlığında `tezgah-dsh-statusline` |

Codex geçidi; Bash, `exec_command`, `apply_patch`, Düzenle/Yaz, MCP araçları,
ve alt ajan çağrılarını diğer barındırıcılarla aynı kontrolden geçirerek çalıştırır. Claude'da,
atıf yasağı mekanik olarak da uygulanır: `attribution` ayarı
boşaltılır (`commit`, `pr`, `sessionUrl`), böylece commit ve PR kredileri
kaynağında kapatılır.

### Durum çubuğu

Her barındırıcı, `tezgah-status`'tan aynı tek satırlık kontrol listesini oluşturur, böylece
birbirlerinden sapamazlar. Önemli olan durumdur: `isim✓` parçasının tamamı renklenir —
kural bu oturumda devrede ve yürürlükte olduğunda **yeşil**, devrede ancak isteğe bağlı
olduğunda (henüz kullanılmadığında) **sarı**, bir acil durum anahtarı (kill switch) onu
kapattığında **kırmızı** ve durum taşımayan bir işaret için **soluk (dim)**. Glif her
durumda yerinde kalır, yani renk ikinci bir kanaldır, tek kanal değil. `idx` grafik hazır olma durumunu
ayrı olarak raporlar (`✓` indekslendi, `↻` bayat, `✗` indekslenmedi, `–` uygulanamaz) ve
`plans N (M blk)` açık planları gösterir. `tezgah-status --legend` anahtarı yazdırır,
`--json` bir kullanıcı arayüzü için aynı segmentleri verir ve `--no-color` (veya `NO_COLOR`)
düz metne zorlar. Claude Code ve Cursor yerel durum çubuğunu renklendirir;
opencode TUI kendi bileşenini renklendirir ve barındırıcı olay veriyolunda (event bus) yenilenir;
dsh Web UI başlık bileşenini renklendirir ve yalnızca sekmesi görünürken yenilenir; Codex
düz dizeyi `systemMessage` içinde gösterir; omp eklentisi renkli satırı
`ctx.ui.setWidget` ile çizer, çünkü diğer yüzeyi olan `setStatus` kaçış dizilerini
siler; satır oturum başlangıcında, oturum geçişinde, tur sonunda ve bir işareti
kaydırabilecek her araç sonucunda yenilenir.

dsh, aynı Claude kanca dosyalarını `dsh-hooks-claude-code` köprüsü üzerinden çalıştırır,
bu nedenle oturum başlatma sözleşmesi, atıf geçidi ve ilk-grep dürtmesi (nudge)
orada da geçerlidir. dsh tek bir `subagent` aracı sunar, bu nedenle yalnızca-grep-kaşifi (grep-only-explorer)
reddi etkisizdir — reddedeceği bir kaşif alt ajanı yoktur. dsh'nin varsayılan
`workspace-write` korumalı alanı (sandbox), kanca alt süreçlerini çalışma alanına ve
platform geçici dizinine hapseder, bu nedenle tezgah, reddedilen bir yazma işleminde başarısız olmak yerine
kanca durumunu (dürtme işaretleri, indeks damgası) oradaki yazılabilir bir geri dönüş (fallback) konumuna yazar. Grafik indeks
işçisi (worker), `codebase-memory-mcp` önbelleğini bu korumalı alanın içinden yazamaz, bu nedenle
`dsh` başlatıcısı, dsh'yi önyüklemeden önce kullanıcının kısıtlanmamış kabuğunda indeksi ısıtır —
yeni bir depo, diğer barındırıcılarda olduğu gibi tam olarak HEAD damgalı olarak indekslenir.
Başlatıcı olmadan önyüklenen bir oturum, ham bir `EPERM` yerine, korumalı alana alınmamış
MCP sunucusunun grafiğe hizmet ettiğine ve indekslemediği bir depo için `index_repository`'ye
ihtiyaç duyduğuna dair net bir rapor alır. Yönetilen
yama bloğu ayrıca, temel bileşimin bağladığı pi-ai adaptöründe iki OpenAI uyumlu LLM rotası bildirir:
yerel `deepseek-official` varsayılanının yanında seçilebilen `openrouter` (`OPENROUTER_API_KEY`) ve `deepseek`
(`DEEPSEEK_API_KEY`). Anahtarlar, başlatma ortamından veya donanım kimlik bilgisi
deposundan çözümlenir; hiçbir anahtar yapılandırma dosyasına girmez. tezgah-setup ayrıca
PATH üzerine (`~/.local/bin/dsh`), `$DSH_HOME` altındaki kurulu CLI'yi bulan bir `dsh`
başlatıcısı yerleştirir, böylece `dsh --profile web` herhangi bir dizinden çalışır.

dsh'nin bir komut durum çubuğu yoktur, bu nedenle tezgah bunu bir Web UI eklentisi olarak sunar:
`tezgah-dsh-statusline`. Bunun barındırıcı yarısı, oturumun çalışma alanı için `tezgah-status` dizesini
kimliği doğrulanmış bir `/api/tezgah.status` rotası üzerinden (renkli görünüm için
`?format=json` ile) sunar; tarayıcı yarısı ise bunu oturum başlığında, duruma göre renklendirilmiş
ve üzerine gelindiğinde/tıklandığında açılan bir gösterge (legend) ile işler ve yalnızca
sekme görünürken yeniler. `tezgah-setup`
eklentiyi web profiline bağlar ve `profiles/web/cordis.patch.yml` içinde yönetilen bir satırla
etkinleştirir (yalnızca web içindir, çünkü barındırıcı yarısı yalnızca web'e özgü `connection`
hizmetini enjekte eder); hiç `web` önyüklemesi yapmamış bir profil, yarım yazılmak yerine
bir ipucu ile atlanır. `headless` modunda, kancalar köprüsü
SessionStart sözleşmesini kendi takip eden sırası olarak enjekte eder (tek seferlik görev zaten
ilk mesaj olduktan sonra `agent/session-start` ayrılmış olarak `agent.inject()` çağrısı yapar),
bu nedenle `dsh --profile headless "<task>"` fazladan bir sıra harcar ve kelimesi kelimesine
cevap bekleyen bir istem için, görevin cevabı yerine modelin sözleşmeye verdiği tepkiyi
yazdırır; etkileşimli web oturumları bundan etkilenmez.

`bin/tezgah-setup --install` ayrıca `orx` PATH üzerindeyken Claude,
Codex, opencode ve Cursor için `orx install-skills` komutunu tetikler, böylece araştırma kuralının
yükleyeceği bir kılavuzu olur. Shim dosyaları orx'e aittir, bu nedenle tezgah yalnızca bu yükleyiciyi
çalıştırır ve bunları asla kaldırma (uninstall) listesine eklemez. dsh'nin bir orx donanımı yoktur;
oradaki araştırma kuralı kabukta `orx skill` komutuna geri döner.

Claude eklentisi ayrıca iki salt okunur ajan sunar. `agents/tezgah-explorer.md`
grafikten kod keşfi yapar ve `dosya:satır` kanıtı döndürür;
`agents/tezgah-reviewer.md` bir diff'i `detect_changes` ile etki kümesine
dönüştürür ve ardından gerçek kusurları arar. Her ikisinin de yazma ve komut
araçları devre dışı bırakılmıştır; çıktıları tavsiye niteliğindedir.

### Uygulama analizi

`analyze-app`, çalışan bir uygulamayı erişilebilirlik ağacından yönlendirir.
Varsayılan döngü; aç, ağacı oku, harekete geç, konsolu/ağı/günlükleri gözlemle ve
ağacı yeniden oku şeklindedir — ekran görüntüsü, ağacın yanıtlayamadığı durumlar
(tuval, oyun, animasyon, piksel düzeyinde görsel regresyon) için açık bir eylemdir. Yetenek,
tüm barındırıcılar için tek bir yoldur; altındaki sunucular `hooks/tezgah_apps.py` içinde
paylaşılan tek bir spesifikasyondur:

| Sunucu | Hedef | Bağlantı yöntemi |
|---|---|---|
| `playwright` (`@playwright/mcp`) | web sayfaları, `browser_*` araçları | opencode, Codex, Cursor, Claude (eklenti `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS Simülatörü / Android emülatörü, `mobile_*` araçları | aynı |
| `chrome-devtools` (isteğe bağlı, `--devtools`) | web performans izleri, derin ağ, kaynak eşlemeli (source-mapped) konsol | aynı |

Tarayıcı varsayılan olarak **izole** bir profil çalıştırır, bu nedenle bir çalıştırma asla
gerçek Chrome durumunuza dokunmaz; oturum açılmış bir akışı analiz etmek varsayılan bir durum değil,
kasıtlı bir eklemedir (`--cdp-endpoint` veya Playwright uzantısı). Ekran görüntüleri,
izler ve ağaç dökümleri `~/.cache/tezgah/apps` dizinine iner (`TEZGAH_ARTIFACTS` ile geçersiz kılınabilir)
ve ajan satır içi görüntü baytları değil, bir yol (path) alır.
Sunucular `npx` üzerinden çalışır, bu nedenle node'a ihtiyaç duyarlar ancak kendi kurulumlarına gerek yoktur;
`tezgah-setup --install --devtools` isteğe bağlı web tanılama sunucusunu ekler.
dsh, aynı iki sunucuyu `dsh-mcp-client` köprüsü üzerinden bağlar
(`serverName` / `command` / `args` / `env`, yayınlanan yapılandırma şemasına karşı onaylanmıştır)
ve Claude bunları eklentinin `.mcp.json` dosyasından alır
(`claude plugin details tezgah` MCP sunucularını 2 olarak listeler ve her ikisi de bağlanır).
`mobile-mcp` daha yüksek sürtünmeli yarıdır: macOS Erişilebilirlik / Ekran Kaydı izni isteyebilir
ve görünüm ağacı yük altında düşebilir, bu nedenle yetenek bir ekran görüntüsüne geri dönmeden önce
ağacı yeniden dener.

CI, her iki sunucu için de deterministik bir el sıkışma (handshake) çalıştırır (tarayıcı yok, cihaz yok):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. İsteğe bağlı iki yerel
duman testi (smoke test) daha ileri gider: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` Playwright MCP'yi
başlatır, gezinir ve ekran görüntüsü olmadan anlık görüntüyü okur;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` Mobile MCP'yi başlatır, görünüm ağacı
araçlarını kontrol eder ve bir cihazı listeler. Node, bir tarayıcı derlemesi veya bir cihaz
eksik olduğunda `SKIP: ...` yazdırırlar.

<a id="install"></a>

## Kurulum

Python 3.8+ gerektirir. dsh barındırıcısı için ve `pnpm` ile web durum çubuğu için node + npm gereklidir.
İsteğe bağlı entegrasyonlar zarif bir şekilde düşürülür (degrade gracefully):
PATH üzerindeki `codebase-memory-mcp` grafiğe güç sağlar; bir model anahtarı `consult`
ve `codegen`'e güç sağlar — varsayılan olarak OpenRouter (`OPENROUTER_API_KEY` veya
`~/.config/openrouter/key`) veya `--provider deepseek` ile DeepSeek API
(`DEEPSEEK_API_KEY` veya `~/.config/deepseek/key`); ve OpenResearch'ün `orx`'i
PATH üzerinde araştırma kuralına yönlendireceği bir şey verir. Seçilen sağlayıcının anahtarı
eksik olduğunda, tezgah mış gibi yapmak yerine bunu söyler.

Klonlayın, ardından algılanan her barındırıcıyı tek geçişte devreye alın:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install` ayrıca eksik olan isteğe bağlı araçları, her satıcının kendi yükleyicisini
**ağ üzerinden** çalıştırarak kurar: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(`npx` aracılığıyla ana profili) ve dsh ihtiyaç duyduğunda `pnpm` (`npm` aracılığıyla) —
`curl ... | sh` dahildir. Hiçbiri sudo gerektirmez; çalıştırma
`~/.config/tezgah/install.log` dosyasına kaydedilir. `--dry-run` ile önizleyin,
`--no-deps` ile atlayın (CI'da kullanışlıdır) veya `--deps` ile yalnızca araçları kurun. Araçlar
`~/.local/bin` veya `~/.cargo/bin` dizinine iner, bu nedenle PATH üzerinde olmaları için
yeni bir kabuk gerekebilir; tezgah'ın kendi kontrolleri ne olursa olsun bu dizinlere bakar,
bu nedenle etkileşimli olmayan bir kabuk yine de onları mevcut olarak raporlar.

Eğer önceki bir kurulum zaten mevcutsa, önce onu içe aktarın — silinmez, kenara taşınır:

```bash
bin/tezgah-setup --adopt
```

Claude Code kendi eklenti kanalı üzerinden kurulur:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Gerektiğinde kurulumu açıkça sınırlandırın:

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Günlük kullanım

Çalıştırılacak bir şey yok: kurallar bir barındırıcı başladığında yüklenir. Birkaç komutu
bilmekte fayda var:

| Komut | Amaç |
|---|---|
| `bin/tezgah-setup` | Barındırıcı başına nelerin devrede olduğunu raporlar |
| `bin/tezgah-status [PATH]` | Kuralların o depoda aktif olup olmadığını gösterir |
| `bin/tezgah-setup --status [PATH]` | Devrede olan/kullanılan kontrol listesini yazdırır |
| `bin/tezgah-setup --deps [--dry-run]` | Eksik isteğe bağlı araçları kurar (orx, cursor-agent, dsh) |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Donanım disk kullanımını raporlar; `--clean` eski indeks günlüklerini siler ve opencode veritabanını vakumlar; `--prune-sessions` boşta kalan oturumları siler (veritabanını gerçekten küçülten tek eylem) |
| `/plan-add` | Bir iş parçasını izlenen bir plana dönüştürür |
| `/plan-status` | Açık planları özetler ve bir sonrakini seçer |
| `/plan-sync` | Biten planları kapatır |
| `bin/tezgah-setup --version` | Eklenti sürümünü yazdırır |
| `bin/tezgah-setup --uninstall` | Yalnızca tezgah'ın sembolik bağlantılarını, barındırıcı kanca girişlerini ve dsh yönetilen bloğunu kaldırır |

<a id="configuration"></a>

## Yapılandırma

Tezgah yalnızca yapılandırılmış kök dizinleri altında devreye girer; başka herhangi bir yerde sessizdir.

- Varsayılan kök dizin: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (yol ayırıcı liste) tek seferlik kullanımlar ve CI için dosyayı geçersiz kılar.

Acil durum anahtarları (kill switches) `~/.config/tezgah/` içinde bulunur. Her biri kendi kuralını
oturuma enjekte edilen metinden çıkarır, böylece kural gerçekten durur:

| Anahtar | Neyi kapatır |
|---|---|
| `exec-mode.off` | Türkçe, sonuç odaklı raporlamayı |
| `ponytail-auto.off` | minimal kod kuralını |
| `spec-off` | inşa etmeden önce spesifikasyon kuralını |
| `consult-off` | harici ikinci görüş kuralını |
| `research-off` | araştırma görevlerini OpenResearch'e yönlendirmeyi |
| `orchestrate-off` | alt ajan delegasyonunu (delege etme satırı ekler) |
| `reminder-off` | her turdaki hatırlatıcı metnini |
| `pretooluse-off` | PreToolUse geçidinin kendisini (atıf, kaşif, grep dürtmesi) |

Depo başına, `.no-ponytail`, `.no-cbm` ve `.no-lessons` sırasıyla minimal kod
kuralını, kod grafiği kuralını (ve otomatik indekslemesini) ve dersler defterini (lessons ledger) kapatır.

Kullanıcı bir hatayı işaretlediğinde, ajan deponun
`.tezgah/lessons.md` dosyasına tek satırlık bir ders ekler; en son satırlar oturum başlangıcında
enjekte edilir, böylece aynı hata sessizce tekrarlanamaz.

<a id="cost"></a>

## Maliyet

Tahmin edilmemiş, bu makinede (macOS, Python 3.10) ölçülmüştür:

- **Bağlam (Context).** Bir oturum başlangıcı ~4.8 KB (~1.2k token) sözleşme metni enjekte eder.
  Codex'te her turda 480 baytlık bir hatırlatıcı yer alır; Claude ve diğer barındırıcıların
  tur başına kancası yoktur, bu nedenle tur başına maliyetleri sıfırdır. Tam `tezgah-contract`
  yeteneği (~25k karakter) yalnızca bir görev onu yüklediğinde ödenir. opencode'da
  sözleşme ~5.8 KB'lık bir talimat dosyası olarak gönderilir. opencode aksi takdirde
  her oturumun sistem istemine ~53 KB'lık yetenek adı/açıklaması/konumu metni enjekte ederdi;
  tezgah bu listeyi reddeder (`permission.skill = deny`) ve bunun yerine oluşturulmuş
  ~16 KB'lık bir yetenek yönlendiricisi gönderir, böylece bir yetenek yönlendiriciden
  `SKILL.md` yolu okunarak bulunur.
- **Gecikme (Latency).** Kancalar ayrı Python süreçleridir, bu nedenle ~19 ms'lik yorumlayıcı
  başlangıcı baskındır. Bunun üzerine, oturum başlangıcı ~25 ms, geçitli bir araç çağrısı
  (Bash/Grep/Task) ~9 ms ve Codex'in Stop segmenti tur başına ~15 ms ekler.
- **Disk.** Kurulum ~58 ms sürer ve tezgah'ın yeniden yazdığı her dosya bir kez
  `<dosya>.tezgah-bak` olarak saklanır.

Bunun karşılığı, çağırıcı (caller) sorularında ortaya çıkar. Bir gerçek depoda, varsayılan bir `grep`
ilgili klasörü yoksaydı ve hiçbir şey bulamadı; yoksayma devre dışı bırakıldığında
3.95 saniye sürdü ve yine de tanımları çağrı siteleriyle karıştırdı. Kod grafiği
aynı soruyu 16 ms'de yanıtlayarak yalnızca 8 gerçek çağrı sitesini listeledi.

opencode ayrıca uzun oturumlu bağlam hijyeni için donatılmıştır: `tezgah-setup --install`,
eski araç sonuçlarının her adımda yeniden gönderilmek yerine istemden temizlenmesi için
`compaction.prune` ayarını yapar ve bir `watcher.ignore` listesi dosya izleyicisini
`.git`, `node_modules` ve derleme dizinlerinden uzak tutar. Her ikisi de birleşir — açık bir kullanıcı değeri
kazanır. Bu önemlidir çünkü opencode yalnızca modelin bağlam sınırına yakın bir yerde
otomatik sıkıştırma yapar (1M token'lık bir model için yaklaşık 980k), bu nedenle budama (pruning) olmadan
çalışma seti yüz binlerce token'a ulaşır. `bin/tezgah-doctor` ortaya çıkan disk ayak izini raporlar;
`--prune-sessions DAYS` opencode CLI aracılığıyla boşta kalan oturumları siler, bu
veritabanını gerçekten küçülten tek eylemdir — VACUUM tek başına bunu yapamaz, çünkü sayfalarının tümü canlıdır.

<a id="development"></a>

## Geliştirme

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI hem Python 3.10 hem de 3.12 üzerinde çalışır. Kurulu bir Claude kopyasını
bu checkout'tan yenilemek için `bin/tezgah-setup --sync` kullanın ve manifestoyu
`claude plugin validate .claude-plugin/plugin.json` ile doğrulayın. Sürümü yükseltirken,
`.claude-plugin/plugin.json` ve `.claude-plugin/marketplace.json` dosyalarını
birlikte güncelleyin — birbiriyle uyuşmalıdırlar.

`codebase-memory-mcp` kullanıcı tarafından kurulur. Orca'nın kancaları ve dosyaları
bu projenin bir parçası değildir ve dokunulmadan bırakılır. Claude, her zaman açık olan
çekirdeği SessionStart kancasından alır; `output-styles/tezgah.md`, eklenti çıktı stillerini
yükleyen derlemeler için bir kopyadır, bu nedenle kanca yetkili yoldur.

<a id="contributing"></a>

## Katkıda bulunma

Küçük, tek amaçlı değişikliklerin kabul edilmesi en kolay olanıdır. Bir kural,
gerçekten barındırıcıya özgü olmadığı sürece paylaşılan çekirdeğe (`hooks/`) aittir;
bir barındırıcı farkı, `hosts/<name>/` altındaki adaptörüne aittir. Diff'i doğru kalacak
şekilde olabildiğince kısa tutun — projenin kendi minimal kod kuralı proje için de geçerlidir.

Bir pull request açmadan önce, CI'ın çalıştırdığı aynı üç kontrolü çalıştırın:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff`, tek geliştirme bağımlılığı olan `requirements-dev.txt` dosyasından gelir
(`pip install -r requirements-dev.txt`).

<a id="security"></a>

## Güvenlik

Güvenlik açıklarını herkese açık bir issue yerine GitHub'ın güvenlik danışma belgeleri
(**Security** sekmesi → **Report a vulnerability**) aracılığıyla gizli olarak bildirin.

tezgah kabuk kancaları çalıştırır, barındırıcı yapılandırması yazar ve her oturuma
metin enjekte eder, bu nedenle bir kancanın saldırgan kontrollü kodu yürütmesine neden olan,
bir yapılandırma dosyasına anahtar sızdıran, bir korumalı alanı genişleten veya depo içeriğinin
talimat metnine yükselmesine izin veren her şey kapsam dahilindedir. Barındırıcıyı,
tezgah sürümünü (`bin/tezgah-setup --version`) ve minimal bir yeniden üretimi (reproduction) ekleyin.

<a id="license"></a>

## Lisans

Kök dizindeki `LICENSE` (MIT) tezgah'ın kendi dosyalarını kapsar. `skills/ponytail` ve
`skills/no-ai-slop`, `NOTICE` içinde kaydedilen kendi MIT koşulları altında sağlanmaktadır.
