<p align="center">
  <a href="README.md">English</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.tr.md">Türkçe</a>
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
  <a href="#benchmark">Benchmark</a> &bull;
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
  Deneyin ihtiyaç duyduğu alan bilgisi de birlikte gelir: vendor edilen
  `AI-research-SKILLs` kütüphanesi (98 yetenek, 23 kategori, MIT) `ai-research` yeteneği
  olarak kurulur ve aşama indeksinden tek tek okunur.
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

| Barındırıcı | Bağlantı yöntemi |
|---|---|
| **omp** (oh-my-pi) — birincil | `~/.omp/agent`: yönetilen `RULES.md` her zaman açık bloğu, yetenekler, oluşturulmuş alt ajanlar, `mcp.json` ve istem başına kuralları devreye alan, araçları geçit denetiminden geçiren, kanıt kaydeden ve Stop kuralını çalıştıran bir uzantı (`hooks/pre/tezgah-hook.ts`); bağlantı `tezgah-setup` tarafından denetlenir |
| **Claude Code** | yerel eklenti pazarı: kancalar (hooks), komutlar, iki salt okunur ajan, çıktı stili |
| **opencode** | eklenti + talimatlar + MCP + oluşturulmuş yetenek yönlendiricisi (yerel yetenek listesi reddedilir), ilk mesajda depo otomatik indeksleme |
| **Codex** | `hooks.json` + yetenekler + MCP, bir `PreToolUse` geçidi dahil |
| **Cursor** | `hooks.json` + yetenekler + MCP |
| **dsh** | Claude Code kanca köprüsü + yönetilen yama bloğu (kancalar, MCP, LLM rotaları, ağaç dışı bir Web durum çubuğu) |

Codex geçidi; Bash, `exec_command`, `apply_patch`, Düzenle/Yaz, MCP araçları,
ve alt ajan çağrılarını diğer barındırıcılarla aynı kontrolden geçirerek çalıştırır. Claude'da,
atıf yasağı mekanik olarak da uygulanır: `attribution` ayarı
boşaltılır (`commit`, `pr`, `sessionUrl`), böylece commit ve PR kredileri
kaynağında kapatılır.

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

Bir terminalde, argümansız çalıştırılan bu komut bunun yerine sihirbazdır: hangi
barındırıcıların devreye alınacağını, kök dizinleri, eksik isteğe bağlı araçların kurulup
kurulmayacağını ve isteğe bağlı DevTools MCP'nin bağlanıp bağlanmayacağını sorar, planı
yazdırır ve yalnızca evet sonrasında yazar. Bayraklar sihirbazın varsayılanlarıdır, bu
nedenle `--wizard --hosts omp` yalnızca geri kalanını sorar. Borulanmış, ajan veya CI
çalıştırmasında asla istem gösterilmez — tıpkı önceden olduğu gibi raporu yazdırır.

`--install` ayrıca eksik olan isteğe bağlı araçları, her satıcının kendi yükleyicisini **ağ
üzerinden** çalıştırarak kurar: `orx` (`openresearch.sh/install.sh`), `cursor-agent`
(`cursor.com/install`), `dsh` (`npx` aracılığıyla ana profili) ve dsh ihtiyaç duyduğunda
`pnpm` (`npm` aracılığıyla) — `curl ...
| sh` dahildir. Hiçbiri sudo gerektirmez; çalıştırma `~/.config/tezgah/install.log`
dosyasına kaydedilir. `--dry-run` ile önizleyin, `--no-deps` ile atlayın (CI'da
kullanışlıdır) veya `--deps` ile yalnızca araçları kurun. Araçlar `~/.local/bin` veya
`~/.cargo/bin` dizinine iner, bu nedenle PATH üzerinde olmaları için yeni bir kabuk
gerekebilir; tezgah'ın kendi kontrolleri ne olursa olsun bu dizinlere bakar,
bu nedenle etkileşimli olmayan bir kabuk yine de onları mevcut olarak raporlar.

Eğer önceki bir kurulum zaten mevcutsa, önce onu içe aktarın — silinmez, kenara taşınır:

```bash
bin/tezgah-setup --adopt
```

Claude Code da aynı betikle kurulur - eklenti manifesti yerel ve sürüm kontrolü dışında bir dosyadır:

```bash
bin/tezgah-setup --install --hosts claude
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
| `bin/tezgah-setup` | Terminalde: kurulum sihirbazı; boru hattında veya CI'da: barındırıcı başına nelerin devrede olduğunu raporlar |
| `bin/tezgah-setup --wizard` | Kurulum sihirbazını her yerde zorlar; `--report` raporu zorlar |
| `bin/tezgah-status [PATH]` | Kuralların o depoda aktif olup olmadığını gösterir |
| `bin/tezgah-setup --status [PATH]` | Devrede olan/kullanılan kontrol listesini yazdırır |
| `bin/tezgah-setup --deps [--dry-run]` | Eksik isteğe bağlı araçları kurar (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status\|claim` | Bir araştırma hattını kurar ve denetler: state, findings, claims ve protokol-sonuç kuralı |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Donanım disk kullanımını raporlar; `--clean` eski indeks günlüklerini siler ve opencode veritabanını vakumlar; `--prune-sessions` boşta kalan oturumları siler (veritabanını gerçekten küçülten tek eylem) |
| `/tezgah:plan-add` | Bir iş parçasını izlenen bir plana dönüştürür |
| `/tezgah:plan-status` | Açık planları özetler ve bir sonrakini seçer |
| `/tezgah:plan-sync` | Biten planları kapatır |
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

<a id="benchmark"></a>

## Benchmark

Bu sözleşme işi gerçekten iyileştiriyor mu, yoksa yalnızca iyileştirmesi gerekiyormuş gibi
mi görünüyor? Bu, iddia edilmek yerine ölçülür: ajanın varlığından haberdar olmadığı gizli
denetimler, barındırıcının kendi kullanım kaydından alınan maliyet ve başarısızlık olarak
puanlanan yan düzenlemeler. Enstrüman - kollar, ön kayıt ve `bench.py` - `benchmarks/lab`
branch'inde durur; yani bu branch sonuçları taşır, laboratuvarı değil. Çalıştırma
kimlikleriyle birlikte tam çalışma OpenResearch projesi `tezgah-harness-research` içindedir.
Aşağıdaki her rakam bir çalıştırma günlüğüdür.

| Blok | Çalıştırma | Neyi kesinleştirdi |
|---|---|---|
| iki barındırıcı, 28 görev, k=3 | 336 | `omp+tezgah` 0.95 ile `opencode+tezgah` 0.96 aralıkları örtüşür ve çözülen görev başına maliyetleri aynıdır; çıplak kollarda omp daha ucuzdur ($0.0047 karşısında $0.0074 CPS), bu nedenle günlük sürücü, kaliteden hiçbir maliyet olmadan omp'tur |
| zor aile, 5 görev, k=5, iki model ailesi | 200 | havuzlanmış, dört kolun üçü 40/50'de buluşur: bu boyutta bir harness etkisi yoktur ve ilk modelin ürettiği tek sinyal ikinci modelde tersine döndü |
| geçit ailesi, geçit devrede | 36 | hiçbir kol kısa yol yolunu seçmedi; geçit mekanizması doğrudan doğrulanır (bir skip düzenlemesi reddedilir), iş üzerindeki etkisi henüz ölçülmemiştir |
| madde ablasyonu, ayırt eden iki kural, k=8 | 160 | sözleşme kolları 23/32 (0.72) geçerken çıplak çapa 12/32 (0.38) geçer |

**Tam olarak modelin varsayılanının yanlış olduğu yerde yardımcı olur.** `c04` (yalnızca
sözleşmenin yanıtı Türkçe yaptığı bir İngilizce istem) sözleşmeyle 9/16, sözleşmesiz 0/16
okur; `h02` (görünür paketi her iki durumda da yeşil olan bir para sözleşmesi) 14/16'ya
karşı 12/16 okur. Kapatılacak bir boşluğun olmadığı yerde — 25 pilot görevin 22'si her kolda
her tekrarda geçti — bir benchmark yalnızca null raporlayabilir.

**Onu iki madde taşır.** Madde 1'i kaldırmak `c04`'ü 0/8'e, yani çıplak çapanın kendi
puanına götürürken `h02`'yi neredeyse hiç oynatmaz. Madde 3'ü kaldırmak `h02`'yi 2/8'e —
çıplak çapanın 6/8'inin altına — götürür çünkü madde 3, en kısa tamam-görünen yolda durmayı
yasaklar ve o görevde en kısa yol, belgelenmiş kuralı çiğnerken görünür paketi geçen tek
satırlıktır. Madde 2 ve 4 ölçülebilir hiçbir şeyi oynatmaz.

**Maliyet kaliteyi izler.** Çözülen görev başına: tam sözleşmeli düğümde $0.0078 karşısında
$0.0097, eksi-ponytail düğümünde $0.0043 karşısında $0.0087. Sözleşme kolları daha fazla
görev çözer, bu nedenle çözülen her görev daha ucuza gelir; toplam harcama daha yüksektir ve
benchmark bunu netleştirmek yerine satır başına kaydeder.

Bunun göstermediği şey: burada ölçülmeyen kod kalitesi, inceleme emeği veya
sürdürülebilirlik; 36 devreye alınmış çalıştırmada hiçbir kol kısa yola uzanmadığı için
geçidin bir kolun seçimleri üzerindeki etkisi; veya bir madde sırası — `k=8` hücre başına 8
çalıştırmayla bir yönü sabitler. Baştan sona tek bir sağlayıcı ve tek bir fikstür paketi
vardır ve ablasyon turları tek bir model ailesinde çalışır. İkinci bir model ailesi 28
görevlik null'ı tam olarak yeniden üretir (51/56 karşısında 51/56), bu da ilk okumanın bir
model artefaktı olmadığını gösterir.

<a id="cost"></a>

## Maliyet

Bu makinede (macOS, Python 3.10) ölçülmüştür, tahmin edilmemiştir. `tezgah-setup` canlı
bütçeyi yazdırır — buraya kopyalanmış bir rakama güvenmek yerine onu orada okuyun; daha
önceki bir revizyon kurduğundan daha küçük bir çekirdek bandını alıntılamaya tam da bu
şekilde varmıştı.

| Bant | Maliyeti |
|---|---|
| Oturum başlangıcı | her zaman açık sözleşme (invariantlar artı isteğe bağlı kural başına tek satırlık bir işaretçi): bu makinede ve yetenek setinde ~1.5k token sözleşme metni ve ~1.4k yetenek üst verisi; koşullu kurallar (spec, consult, research, graph) yalnızca istemi eşleşen turda ~0.7k ekler |
| Tur başına | kısa bir hatırlatıcı (~0.2k token) artı eşleştiğinde devreye alınan kural; kancalar ayrı Python süreçleridir, bu nedenle ~19 ms yorumlayıcı başlangıcı temeldir — bir tur ~31 ms ekler, oturum başlangıcı ~50-81 ms, geçitli bir araç çağrısı (Bash/Grep/Task) ~24-25 ms ekler. opencode'un istem zamanı kancası yoktur, bu nedenle sıfır öder |
| İsteğe bağlı | tam `tezgah-contract` yeteneği (~6.6k token), yalnızca bir görev onu yüklediğinde ödenir |
| MCP şemaları | en büyük bant ve hiçbir statik raporun görmediği bant: tek başına graph sunucusu 15 araç / 24,508 bayt (~6.1k token) bildirir ve barındırıcı şemaları isteğe bağlı getirmediği sürece her isteğe biner. `tezgah-setup --mcp-schemas` bunu ölçer |
| Disk | kurulum ~58 ms sürer ve tezgah'ın yeniden yazdığı her dosya bir kez `<file>.tezgah-bak` olarak saklanır |

**Devreye alma tabanı.** Invariantlar her zaman açıktır — yürütme modu, ponytail, tüm isteği
teslim et, bütünlük, döngü disiplini, dersler defteri ve atıf yasağı — ve güvenlik kuralı
("geri döndürülemez veya dışa dönük eylemler önce açık bir talep gerektirir") bunlardan
biridir, bu nedenle hiçbir zaman bir sınıflandırıcıya bağlı değildir. Her tavsiye
niteliğindeki kural, her zaman açık, eyleme geçirilebilir tek satırlık bir işaretçi tutar;
böylece kaçırılan bir eşleşme yalnızca ayrıntıya mal olur, asla kuralın kendisine değil, ve
başarısız olan bir barındırıcı kancası sözleşmesizliğe değil, işaretçilere artı isteğe bağlı
yeteneğe geri döner. Yanlış negatifler denetlenebilir: her istem
`~/.cache/tezgah/classify.log` dosyasına `armed=<rules|none> chars=<n>` — istem metni yok —
ekler (64 KB üzerinde son 200 satıra kısaltılır) ve beş kanca barındırıcısının tümü aynı
istem için aynı kümeyi devreye alır (`tests/test_context.py::ArmingConformance`).

**opencode farklı şekilde devreye alınır.** İstem zamanı enjeksiyon noktası yoktur, bu
nedenle sözleşme oluşturulmuş bir talimat dosyası olarak gönderilir ve her zaman açık
yönlendiricisi yalnızca bir kodlama oturumunun başvurduğu kovaları listeler, geri kalanını
isteğe bağlı okunan `~/.config/tezgah/opencode-skills.full.md` adresindeki bir işaretçiye
indirger; `permission.skill = deny` opencode'un her yeteneğin üst verisini enjekte etmesini
durdurur. `--install` ayrıca `compaction.prune` ve `watcher.ignore` ayarlarını yapar, eski
araç sonuçlarını her adımda yeniden göndermek yerine istemden temizler — bu olmadan çalışma
seti, opencode modelin sınırına (1M token'lık bir model için yaklaşık 980k) yakın otomatik
sıkıştırma yapmadan önce yüz binlerce token'a büyür. `bin/tezgah-doctor` disk ayak izini
raporlar ve `--prune-sessions DAYS` boşta kalan oturumları opencode CLI aracılığıyla siler;
bu, veritabanını gerçekten küçülten tek eylemdir, çünkü tek başına VACUUM bunu yapamaz.

**Neden karşılığını veriyor.** Gerçek bir depoda varsayılan bir `grep` ilgili klasörü
yoksaydı ve hiçbir şey bulamadı; yoksayma devre dışı bırakıldığında 3.95 saniye sürdü ve
yine de tanımları çağrı siteleriyle karıştırdı; kod grafiği ise aynı soruyu 16 ms'de 8
gerçek çağrı sitesiyle yanıtladı.

<a id="development"></a>

## Geliştirme

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI hem Python 3.10 hem de 3.12 üzerinde çalışır. Kurulu bir Claude kopyasını
bu checkout'tan yenilemek için `bin/tezgah-setup --sync` kullanın ve manifestoyu
`claude plugin validate .claude-plugin/plugin.json` (manifest yerel ve izlenmiyor) ile doğrulayın. Sürümü yükseltirken,
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
