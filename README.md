# Tezgah

Tek bir çalışma sözleşmesini, kullandığın her AI kodlama host'una kuran paket:
**Claude Code, opencode, Codex ve Cursor**. Kurunca hepsi devreye girer; kapatınca
hepsi susar. Tanımlı kök dizinlerin dışında hiçbir şey yapmaz.

Sözleşme metni tek yerde durur (`hooks/tezgah_policy.py`), bir oturuma ne
söyleneceğine tek yerde karar verilir (`hooks/tezgah_context.py`), her host ise
sadece olay adlarını ve çıktı zarfını çeviren ince bir adaptör alır.

---

## Bu nedir, kim kullanır

Aynı repolarda birden fazla AI ajanı kullanan bir geliştirici için. Her host'un
kendi davranışı, kendi kuralları ve kendi "keşif" alışkanlığı var; tezgah bu
dağınıklığı tek sözleşmeye bağlar. Tezgah şunları dayatır:

- **Türkçe yönetici raporlama (BLUF):** cevap Türkçe, önce sonuç; iş/commit
  içeriği İngilizce.
- **Ponytail kod disiplini:** işe yarayan en tembel çözüm; gereksiz soyutlama yok.
- **Kod-grafiği önceliği:** "kim çağırıyor / neyi bozar" soruları grep değil
  `trace_path` / `search_graph` ile.
- **Dış ikinci görüş:** kritik kararda `bin/consult` ile bağımsız modellere danışma.
- **Orkestrasyon:** ana thread karar verir, alt ajanlar uygular; kanıtsız
  "yaptım/test ettim" yok.
- **Planlar katmanı:** `plans/open/*.md` ve PR durumu.
- **Atıf yasağı:** commit/PR gövdesinde `Co-Authored-By` veya model adı geçmez.

Kısaca: aynı repoda hangi host'u açarsan aç, aynı kurallar, aynı dil, aynı
disiplin, aynı doğruluk standardı.

---

## Ne sağlar

| Bileşen | Etki |
|---|---|
| Ortak çekirdek (`hooks/tezgah_paths.py`, `tezgah_policy.py`, `tezgah_context.py`, `tezgah_gate.py`) | Hangi köklerin silahlı olduğu, sözleşme metni, olay başına bağlam, grep/Explore kapısı |
| Claude Code eklentisi | `hooks.json` ile SessionStart/UserPromptSubmit/SubagentStart/PostCompact + PreToolUse; namespaced skill'ler; `statusline.py` |
| opencode eklentisi | JS plugin: grep'te grafiğe itme + kullanım kaydı; `instructions` ile kalıcı sözleşme |
| Codex adaptörü | `~/.codex/hooks.json` (5 olay) + `~/.codex/skills` |
| Cursor adaptörü | `~/.cursor/hooks.json` (7 olay) + `~/.cursor/skills` |
| `bin/consult` | OpenRouter üzerinden bağımsız modellerden ikinci görüş (paralel) |
| `bin/codegen` | Ucuz modele sınırlı taslak yazdırır; repoya yazmaz, sadece diff basar |
| `workflows/` | Claude için `cbm-map`, `cbm-review`, `cbm-impact` grafik harness'ları |
| `bin/tezgah-setup` | Dört host'u algılar, bağlar, eski kurulumu devralır, rapor verir |
| `bin/tezgah-status` | Her host'ta `pony✓ exec✓ · consult○ cbm○ orch○` kontrol listesi |

## Host matrisi

| Yetenek | Claude Code | opencode | Codex | Cursor |
|---|---|---|---|---|
| Kalıcı sözleşme | plugin hook'ları | `instructions` → üretilen dosya | `hooks.json` SessionStart | `hooks.json` sessionStart |
| Tur başına hatırlatma | UserPromptSubmit | (sözleşmede) | UserPromptSubmit | (sessionStart bağlamı) |
| Grep/Explore kapısı | PreToolUse + Explore deny | JS plugin `tool.execute.before` | (tavsiye) | preToolUse + subagentStart deny |
| Kullanım kaydı | statusline transcript | JS plugin `tool.execute.after` | PostToolUse | postToolUse |
| Skill'ler | plugin `skills/` (namespaced) | `~/.config/opencode/skills` | `~/.codex/skills` | `~/.cursor/skills` |
| MCP kaydı | `~/.claude.json` (senin) | `opencode.json` | `config.toml` | `mcp.json` |
| Durum satırı | `statusline.py` | `tezgah-status` | `tezgah-status` | `tezgah-status` |
| Grafik harness | `Workflow(cbm-*)` | elli faz akışı | elli faz akışı | elli faz akışı |

---

## Kurulum

```bash
git clone <bu repo> ~/Projects/tezgah          # herhangi bir yol; yol gömülü değil

# Claude Code (kendi plugin kanalı)
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local

# hepsi (Claude ekstraları + opencode + Codex + Cursor)
~/Projects/tezgah/bin/tezgah-setup --install   # veya --roots ~/work:~/oss --install
~/Projects/tezgah/bin/tezgah-setup --adopt     # bir kez: eski projects-harness / cbm-* hook'larını devre dışı bırakır
```

`--install` idempotenttir; düzenlediği her dosya bir kez `<dosya>.tezgah-bak`
olarak yedeklenir. Argümansız `tezgah-setup` sadece rapor verir; "burada neden
hiçbir şey olmuyor" sorusunun cevabıdır:

```
codex:
    ok   hooks.json wired
    ok   skills linked
   MISS  MCP in config.toml
```

Bilinçli olarak dokunmadığı tek şey `~/.claude/settings.json`'dır. Durum satırı
segmentini kullanmak için şu satırı yapıştır:

```json
"statusLine": { "type": "command", "command": "python3 \"$HOME/.claude/statusline.py\"" }
```

### `--adopt` neyi devralır

Şunları `~/.config/tezgah/adopted/<zaman>/` altına taşır ve onlara çağrı yapan
kayıtları temizler: `~/.codex/projects-harness/`, `~/.codex/hooks.json` içindeki
projects-harness kayıtları, `~/.claude/hooks/cbm-*` ve `settings.json`'daki cbm
kayıtları, eski `~/.codex/bin/{consult,codex-harness-status}` shim'leri. Orca'nın
hook'ları hiç dokunulmadan kalır; Cursor/Claude/Codex hook dosyaları üzerine
yazılmaz, **birleştirilir**.

---

## Faydaları

- **Tek doğruluk kaynağı.** Sözleşme metni tek dosyada; dört host aynı metni görür.
  Bir cümleyi değiştirince dördü de değişir.
- **Host'tan bağımsız doğrulama standardı.** "Yaptım" ancak kanıtla; atıf yasağı;
  BLUF raporlama. Hangi host'ta çalıştığını değiştirirsen davranış değişmez.
- **Grafik önceliği gerçekten işe yarıyor** (aşağıdaki ölçüm): "kim çağırıyor"
  sorusunda grep ya kör kalıyor ya da 3.95s sürüp yanlış cevap veriyor; grafik
  ~16ms'de tam çağrı yerlerini veriyor.
- **Ucuz ve hızlı.** Hook başına marjinal gecikme ölçüldü: SessionStart ~+12ms,
  PreToolUse ~+0.1ms. Installer ~47ms'de idempotent kurar.
- **Güvenli devralma.** Her dosya yedeklenir; eski kurulum silinmez, taşınır;
  Orca entegrasyonu korunur.
- **Kademeli bozulma.** Grafik yoksa veya anahtar yoksa sessizce yanlış davranmaz,
  "grafik yok / dış doğrulama atlandı" der.
- **Kök-scoped.** Tanımlı köklerin dışında sıfır çıktı, sıfır gecikme.

## Sınırları ve dezavantajları

- **Her oturumda bağlam maliyeti var.** SessionStart/PostCompact ~12,489 bayt
  (≈3.1k token, aşağıdaki yöntemle) enjekte eder. opencode'da sözleşme dosyası
  ~12,567 bayt olarak kalıcı bağlamda durur.
- **Turlar arttıkça hatırlatma tekrarlanır.** Claude'da her UserPromptSubmit
  ~1,278 bayt (≈320 token) ekler; 50 turluk bir oturumda ~64KB tekrar eden metin.
- **Codex'te engelleyici kapı yok.** Codex `PreToolUse` sunmadığı için "Explore
  yasak" ve "ilk grep'i engelle" yalnızca Claude/Cursor/opencode'da gerçek;
  Codex'te tavsiye metni olarak kalır.
- **`codebase-memory-mcp` ayrı kurulur.** Yoksa grafik araçları da yoktur; tezgah
  grep'e düşer ve bunu açıkça söyler.
- **`consult`/`codegen` OpenRouter anahtarı ister.** Anahtar yoksa dış doğrulama
  bloklanır (uydurulmaz, atlandığı söylenir).
- **Kurallar sözleşmedir, garanti değil.** Model her zaman uymayabilir. Gerçek
  yaptırım yalnızca engelleyebilen hook'ların olduğu yerdedir.
- **Host config dosyalarını düzenler.** `hooks.json`, `opencode.json`,
  `config.toml`, `mcp.json` değişir; `.tezgah-bak` yedeği alınır.

---

## Benchmark (bu makinede ölçüldü)

Ortam: Apple M1 Pro, macOS 26.5.1, Python 3.10.14, Node v22.23.1,
codebase-memory-mcp 0.10.8. Yöntem: her hook alt süreç olarak 15 kez çalıştırıldı,
duvar-saati `perf_counter` ile ölçüldü; süreler ortalama (p50 parantezde). Token
sayıları kapalı ortamda gerçek tokenizer olmadığı için **tahminidir**:
`chars/4` ve `kelime×1.3` sezgiseli; kesin sayı değil, karşılaştırma içindir.

### Hook gecikmesi

| Ölçüm | Ortalama | Not |
|---|---|---|
| Python başlangıç tabanı (`python3 -c pass`) | 19.3ms | tezgah'nın altındaki zemin |
| Çekirdek import eden bir hook'un tabanı | ~33ms | politika+çekirdek importu dahil |
| Claude SessionStart | 45.5ms (p50 44.9) | tabana göre marjinal **~+12ms** |
| Claude UserPromptSubmit | 44.8ms | aynı sınıf |
| Claude PreToolUse (grep) | 28.6ms | tabana göre **~+0.1ms** |
| Cursor sessionStart | 45.0ms | |
| Cursor preToolUse | 36.2ms | |
| Codex SessionStart | 44.4ms | |
| Kök dışı SessionStart | 33.4ms, 0 bayt çıktı | **inert** |
| Kök dışı PreToolUse | 28.5ms, 0 bayt çıktı | **inert** |

### Bağlam maliyeti (enjekte edilen metin)

| Olay / dosya | Bayt | Kelime | ~token (chars/4) |
|---|---|---|---|
| SessionStart / PostCompact | 12,489 | 1,909 | ~3,120 |
| SubagentStart | 7,983 | 1,195 | ~1,993 |
| UserPromptSubmit (her tur) | 1,278 | 182 | ~320 |
| opencode kalıcı sözleşme dosyası | 12,567 | 1,916 | ~3,140 |

Blok bazında (hangisini kapatırsan ne kadar düşer):

| Blok | Bayt | | Blok | Bayt |
|---|---|---|---|---|
| ORCHESTRATE | 3,732 | | REMINDER | 1,254 |
| EXEC | 3,597 | | PONYTAIL | 1,169 |
| CBM_RULE | 1,995 | | CONSULT | 1,132 |
| WORKFLOWS | 682 | | NO_CBM / NO_CONSULT | 394 / 335 |

Skill'ler isteğe bağlı yüklenir: toplam 40,153 bayt, oturum bağlamına girmez.
`workflows/` 20,808 bayt (yalnız Claude, çağrılınca).

### Grafik vs grep — "build_manifest'ı kim çağırıyor?"

Gerçek, indeksli bir repoda (`aibim-app`, `.engineering/` dahil) ölçüldü:

| Yöntem | Süre | Sonuç | Doğruluk |
|---|---|---|---|
| `rg 'build_manifest'` (varsayılan) | 0.068s | **0 eşleşme** | `.engineering` ignore'da, tamamen kör |
| `rg --no-ignore --hidden` | **3.95s** | 10 satır / 2 dosya / 1,146 bayt | tanım + test çağrıları karışık, çağıran/çağrılan ayrımı yok |
| graph `trace_path` (inbound) | **15.8ms** (p50 16.2, 10 çağrı) | **8 çağrı yeri**, fonksiyon seviyesinde / 204 bayt | yalnız gerçek çağrı yerleri |

Grep'in hızlı görünmesi yanıltıcı: doğru cevabı bulmak için ignore'ı kapatınca
~58 kat yavaşlıyor ve yine de tanım ile çağrıyı ayırmıyor. Grafik, aynı soruyu
~16ms'de ve 6 kat daha küçük bir cevapla veriyor.

### Kapı ve installer

| Ölçüm | Sonuç |
|---|---|
| İlk identifier grep | deny (grafik araçlarına yönlendirir) |
| Aynı oturumda ikinci grep | geçer |
| Explore alt ajanı | deny |
| `tezgah-setup` rapor | 44.8ms |
| `tezgah-setup --install` (idempotent) | 46.7ms |

---

## Nasıl çalışır (dosya haritası)

| Yol | Görev |
|---|---|
| `hooks/tezgah_paths.py` | Tek çözücü: kökler, `codebase-memory-mcp`, consult anahtarı, kill switch'ler, stabil `bin/` yolları |
| `hooks/tezgah_policy.py` | Sözleşme metni (ponytail, EXEC, orkestrasyon, consult, grafik kuralı) |
| `hooks/tezgah_context.py` | Olay başına bağlam, arka plan indeks, açık planlar, kullanım kaydı, durum satırı |
| `hooks/tezgah_gate.py` | Claude+Cursor'un paylaştığı grep/Explore kapı mantığı |
| `hooks/projects-auto-init.py`, `projects-pretooluse.py` | Claude adaptörleri (plugin hook'ları) |
| `hosts/codex/hook.py`, `hosts/codex/hooks.json` | Codex adaptörü |
| `hosts/cursor/hook.py`, `hosts/cursor/hooks.json` | Cursor adaptörü |
| `hosts/opencode/plugins/tezgah.js` | opencode plugin'i (kapı + kayıt) |
| `workflows/*.js` | Claude dinamik grafik harness'ları |
| `skills/` | `harness`, `ponytail`, `no-ai-slop`, `plan-add`, `plan-status`, `plan-sync` |
| `bin/consult`, `bin/codegen` | Dış ikinci görüş ve ucuz taslak |
| `bin/tezgah-setup`, `bin/tezgah-status` | Installer/rapor/devralma ve durum CLI'ı |
| `statusline.py` | Claude durum satırı segmenti |

### Nerede silahlı

`hooks/tezgah_paths.py`, sırayla:

1. `TEZGAH_ROOTS` — `os.pathsep` ile ayrılmış liste (CI ve tek seferlik işler)
2. `~/.config/tezgah/config.json` → `{"roots": ["~/work", "~/oss"], "cbm_bin": "..."}`
3. `~/Projects` — eski kurulum bozulmasın diye varsayılan

Hook'ları app başlatır, etkileşimli shell değil; bu yüzden `.zshrc`'deki env var
onlara ulaşmayabilir — güvenilir kanal config dosyasıdır.

---

## Kill switch'ler

Makine geneli, `~/.config/tezgah/` (eski `~/.claude/` kopyaları da geçerli):
`ponytail-auto.off`, `exec-mode.off`, `consult-off`, `orchestrate-off`,
`reminder-off`, `pretooluse-off`.
Repo başına, kökünde: `.no-ponytail`, `.no-cbm`.

## Host notları

- **opencode** stdout'a bağlam enjekte edemez. Kalıcı sözleşme
  `~/.config/tezgah/opencode-contract.md` dosyasıdır (politikadan üretilir) ve
  `opencode.json` `instructions` alanından okunur; JS plugin kapı ve kaydı ekler.
  Plugin `plugins/` ve `plugin/` altına birden kurulur, çift yüklenmeye karşı
  kendini korur.
- **Cursor** bağlamı `sessionStart.additional_context`, kapıyı `preToolUse` ile
  alır. Kullanıcı kuralları diskte değil arayüzde olduğundan global kanal hook'tur.
- **Codex** Claude'un `hookSpecificOutput` zarfını kullanır; proje bazlı
  `.codex/hooks.json` ve trust hash'leri ellenmez.

## Geliştirme

Kurulan Claude plugin'i kopyadır; `claude plugin update` içeriğe değil sürüme
bakar. Sürümü **iki** dosyada birden yükselt
(`.claude-plugin/plugin.json` ve `.claude-plugin/marketplace.json`), sonra:

```bash
claude plugin marketplace update rizacan-local
claude plugin update tezgah
```

Geliştirirken `bin/tezgah-setup --sync` sürüm yükseltmeden checkout'u kurulu
kopyanın üzerine yazar (yeni, henüz commit'lenmemiş dosyalar dahil). Diğer üç
host symlink ile çalışır, `--install` onları canlı takip eder.

`claude plugin validate .claude-plugin/plugin.json` manifest'i doğrular.

## Kapsam dışı

`codebase-memory-mcp` MCP sunucusunu sen kurarsın; `tezgah-setup` yalnızca
gereken host'a kaydeder ve binary'yi bulup bulmadığını raporlar. Claude'da
`~/.claude.json` içinde kalır.

Orca'nın hook'ları, dört symlink skill'i ve durum satırı scripti bize ait değil,
dokunulmaz.

## Üçüncü taraf

`skills/ponytail` ve `skills/no-ai-slop` vendored MIT skill'leridir; kendi
koşulları geçerlidir (bkz. `NOTICE`). Kök `LICENSE` tezgah'ın kendi dosyalarını
kapsar.
