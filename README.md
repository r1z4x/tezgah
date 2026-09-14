# Tezgah

Yapay zekâ kodlama asistanlarına **tek bir çalışma kuralı seti** verir.
Claude Code, opencode, Codex ve Cursor artık aynı kurallarla çalışır.

Tek cümle: *Hangi asistanı açarsan aç; aynı dilde, aynı disiplinde, aynı
doğrulukta çalışır.*

## Neden var?

Her asistanın kendi alışkanlığı var. Biri Türkçe cevap verir, diğeri İngilizce.
Biri kod ararken `grep` kullanır, diğeri kod grafiğini. Biri test etmeden
"tamam oldu" der. Aynı repoda birden fazla asistan kullanınca davranış sürekli
değişir. Tezgah bu dağınıklığı tek bir sözleşmeye bağlar.

## Ne kazandırır?

- **Türkçe raporlama:** cevap Türkçe, önce sonuç (BLUF). Kod ve commit İngilizce kalır.
- **Az kod:** gereksiz soyutlama yok, işe yarayan en kısa çözüm (Ponytail).
- **Doğru arama:** "kim çağırıyor / neyi bozar" sorusu `grep` yerine kod grafiğiyle.
- **Dış görüş:** kritik kararda bağımsız modellere danışır, sonucu sana söyler.
- **Kanıt:** test edilmeden "yaptım" denmez.
- **Plan takibi:** işler `plans/` altında ve PR durumuyla izlenir.
- **Temiz commit:** commit/PR metnine `Co-Authored-By` veya model adı eklenmez.

## Nasıl çalışır? (basit)

İki parça var:

1. **Ortak kurallar** — tek bir dosyada durur.
2. **Adaptörler** — bu kuralları her asistanın anladığı formata çevirir.

Kuralı bir kez değiştirirsin, dört asistan da aynı şeyi görür.
Tanımlı kök dizinlerin (varsayılan `~/Projects`) dışında hiçbir şey yapmaz.

## Kurulum

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install     # dört asistanı da bağlar
bin/tezgah-setup --adopt       # eski bir kurulum varsa devralır (bir kez)
```

Claude Code kendi eklenti kanalını kullanır:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Kurulumu istediğin zaman tekrar çalıştırabilirsin. Düzenlediği her dosyayı önce
`.tezgah-bak` olarak yedekler.

## Günlük kullanım

Kurduktan sonra ekstra bir şey yapmazsın; asistan açılınca kurallar kendiliğinden
yüklenir. İşine yarayan komutlar:

- `tezgah-setup` — ne kurulu, ne eksik
- `tezgah-status` — bu repoda kurallar aktif mi
- `/plan-add ...` — bu işi plana dönüştür

## Hangi asistanlarda ne kadar çalışır?

| Asistan | Durum |
|---|---|
| Claude Code | Tam: kurallar enjekte edilir, `grep`/Explore engellenir |
| opencode | Tam: kalıcı sözleşme + plugin kapısı |
| Codex | İyi: kurallar enjekte edilir, ama engelleme yok (tavsiye) |
| Cursor | Tam: oturum başında bağlam + `preToolUse` kapısı |

## Avantaj ve dezavantaj

**Avantajları:** Tek doğruluk kaynağı; host'tan bağımsız aynı davranış; "kim
çağırıyor" sorusunda ölçülü şekilde çok hızlı; hızlı kurulum ve kolay geri alma;
grafik ya da anahtar yokken yalan söylemez, "yok" der.

**Dezavantajları:** Her oturumda ~12,5 KB bağlam ekler (≈3.100 token); Claude'da
tur başına ~1,3 KB hatırlatma; Codex'te engelleme yok; `codebase-memory-mcp` ve
OpenRouter anahtarı ayrıca gerekir; kurallar bir sözleşmedir, kesin garanti değil.

## Ölçümler (bu makinede gerçekten ölçüldü)

| Ne | Sonuç |
|---|---|
| SessionStart gecikmesi | 45 ms (Python tabanı 19 ms; marjinal ~+12 ms) |
| PreToolUse gecikmesi | ~+0,1 ms |
| Her oturum bağlam maliyeti | ~12,5 KB (≈3.100 token) |
| `tezgah-setup` | ~47 ms, tekrar çalıştırılabilir |
| "Kim çağırıyor?" — `grep` | 3,95 sn / 10 karışık satır |
| "Kim çağırıyor?" — grafik | 16 ms / 8 net çağrı yeri |

Token sayıları tahminidir (gerçek tokenizer yok); diğerleri duvar-saati ölçümü.

## Geliştirme

```bash
bin/tezgah-setup --sync     # kurulu Claude kopyasını bu checkout ile tazele
claude plugin validate .claude-plugin/plugin.json
```

Sürümü **iki** dosyada birden yükselt: `.claude-plugin/plugin.json` ve
`.claude-plugin/marketplace.json`.

## Kapsam dışı

`codebase-memory-mcp` sunucusunu sen kurarsın. Orca'nın hook'ları ve dosyaları
bize ait değildir, dokunulmaz.

## Lisans

Kök `LICENSE` tezgah'ın kendi dosyalarını kapsar. `skills/ponytail` ve
`skills/no-ai-slop` vendored MIT skill'leridir; kendi koşulları geçerlidir
(bkz. `NOTICE`).
