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

<p align="center"><sub>İngilizce ana kaynaktır; çeviriler geriden gelebilir.</sub></p>

---

Tezgah, çalıştırdığınız her yapay zeka kodlama asistanını — **birincil
barındırıcı olan omp** ve Claude Code, Codex, Cursor, opencode ile DeepSeek'in
dsh donanımı — yapılandırdığınız depo kökleri içinde tek bir çalışma
sözleşmesiyle donatır. Kendi haline bırakıldığında her asistan sapar: biri
Türkçe yanıt verirken diğeri İngilizce yanıt verir, biri grep kullanırken
diğeri bir kod grafiğini sorgular, biri test çalıştırmadan "tamamlandı" der.
Kurallar paylaşılan bir çekirdekte bir kez yer alır; her barındırıcı, bu
kuralları anladığı şekle çeviren ince bir adaptör alır — bir kuralı tek yerde
değiştirdiğinizde her barındırıcıya aynı şekilde ulaşır.

## Neden tezgah

- **Tek sözleşme, altı barındırıcı.** omp, Claude Code, Codex, Cursor,
  opencode ve dsh aynı kuralları görür, çünkü her barındırıcı paylaşılan tek
  bir çekirdeğin ince bir adaptörüdür — kuralı bir kez değiştirin, hepsi alır.
- **"Tamamlandı", kontrolün çalıştığı anlamına gelir.** 15 reddin olduğu bir
  kapı, etkisizleştirilmiş kontrolü durdurur — `--no-verify`, `|| true`,
  `tail`'e yönlendirilmiş bir test, uçuş sırasında eklenen bir skip — ve
  çalıştırmanın destekleyemediği tamamlanma iddiasını engeller.
- **Araştırma kütüphanesiyle birlikte gelir.** Araştırma görevleri,
  bağlamın küçük kalması için tek tek yüklenen 98 becerilik gömülü
  bir kütüphaneyle OpenResearch üzerinden yürütülür.
- **Her kuralın bir kapatma anahtarı vardır.** On altı kapatma anahtarı — ve
  depo başına işaretler — kuralın metnini oturumdan kaldırır; böylece kural
  yalnızca kapalı görünmez, gerçekten durur.
- **Harekete geçirebileceğiniz yanıtlar.** Yanıtlar Türkçedir ve sonuçla
  başlar; bir liste en fazla beş sıralı madde gösterir; bir tahmin tahmin
  olarak adlandırılır; bir hata konum, neden, çözüm olarak okunur.

<a id="install"></a>

## Kurulum

Tek satır, macOS, Linux veya WSL'de (Python 3.10+, `curl`, `tar`). Son sürümü
indirir, sha256'sını doğrular ve bulduğu her barındırıcıyı kurar:

```bash
curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
```

Ya da npm ile: `npm i -g @r1z4x/tezgah && tezgah --install`.

Kurulumu kodlama asistanınıza yaptırmak isterseniz bunu omp, Claude Code,
Codex, Cursor veya opencode'a yapıştırın (istem İngilizce; asistan her dilde
anlar):

```text
Install tezgah (https://github.com/r1z4x/tezgah) on this machine and verify it.

1. Check the prerequisites: python3 --version must be 3.10 or newer, and curl
   and tar must exist. If one is missing, stop and tell me which.
2. Run the installer exactly as published - do not edit it or pipe it anywhere else:
   curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
   Its output must contain "verified tezgah-<version>.tar.gz" (the sha256
   check). If it does not, stop and show me the output.
3. Verify: run ~/.local/share/tezgah/current/bin/tezgah-setup --version and
   ~/.local/share/tezgah/current/bin/tezgah-setup --report, and show me every
   line that says MISS.
4. Tell me which hosts were armed, which repository root was configured
   (default ~/Projects - if my code lives elsewhere, ask me for the directory and
   run ~/.local/share/tezgah/current/bin/tezgah-setup --roots <dir> --install),
   and that I must restart each assistant for the hooks to load.
Do not change any other file and do not uninstall anything.
```

Sürüm sabitleme, Windows (`packaging/install.ps1`), çevrimdışı tarball,
yükseltme ve isteğe bağlı entegrasyonlar [docs](docs/README.md) altındadır.

## Desteklenen barındırıcılar

**omp** (birincil barındırıcı; tezgah buna göre geliştirilir ve doğrulanır), **Claude Code**, **Codex**, **Cursor**, **opencode**, **dsh** — paylaşılan tek çekirdeğin ince adaptörleri.

## Ayrıntılar nerede

Kapı, kanıt defteri, barındırıcı adaptörleri, yapılandırma ve geliştirme [docs/README.md](docs/README.md) içindedir; soru başına bir sayfa.

## Lisans

MIT — bkz. [LICENSE](LICENSE).
Katıştırılmış beceriler (`ponytail`, `no-ai-slop`, `i-have-adhd`) kendi MIT koşullarıyla gelir; bkz. [NOTICE](NOTICE).
