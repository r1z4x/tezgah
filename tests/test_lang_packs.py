"""The language packs (hooks/lang/<code>.json) the detectors are built from.

Plan 086 S5 (research line `orchestrator-flow-audit`, data/S5.md, V1+V4): the
Turkish half of every detection class was inlined beside the English half in
six modules, so no other language could arm a class without regex edits. The
packs hold that vocabulary as data, one file per language, and every reader
compiles the union of the shipped packs. Four things are held here:

- parity: every pack answers every class key, with the same shape, so a reader
  never meets a pack that lacks the key it reads;
- no regression: the fixture probe of S5 (scripts/s5/probe.py, en and tr rows)
  answers what the inlined regexes answered before the split - the golden
  values below were recorded from the pre-change hooks;
- S5 F8: the tr reply markers no longer pass Spanish, French or Dutch prose as
  Turkish (the shared short words de, da, en, ne, ya, her, mi left the list);
- a language is one data file: a German pack dropped into a copy of hooks/
  arms the German rows of the probe that stay dark without it. No `de` pack
  ships - its vocabulary would be unmeasured - so the shipped packs are en and
  tr, and the German rows are pinned dark below.

The probe sentences are a fixture (hand-written one-liners), evidence about
the code path, not about any real user's prompts.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

sys.path.insert(0, support.HOOKS)
import tezgah_context as tc  # noqa: E402
import tezgah_integrity as ti  # noqa: E402

LANG_DIR = os.path.join(support.HOOKS, "lang")


def load(code):
    with open(os.path.join(LANG_DIR, code + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def shape(node, path=""):
    """{dotted key: value type} of a pack, nested maps walked."""
    out = {}
    for key, value in node.items():
        here = path + "." + key if path else key
        out[here] = type(value).__name__
        if isinstance(value, dict):
            out.update(shape(value, here))
    return out


# What the probe's en and tr rows answered before the vocabulary moved into the
# packs (recorded from the pre-change hooks), and the German rows, dark with no
# German pack.
GOLDEN = {
    "residual": {"Açık kalanlar": True, "Open items": True, "Next steps": True,
                 "Offene Punkte": False},
    "sycophant": {"Haklısın, düzelttim.": True, "You're right, fixed.": True,
                  "Evet, haklısın.": True,
                  "Du hast recht, ich habe es behoben.": False},
    "closer": {"Hope this helps": True, "Başka bir şey gerekirse söyle.": False},
    "claims": {"Fixed, all tests pass.": (True, False),
               "Düzelttim, testler geçti.": (True, False),
               "Testler geçti mi?": (False, False), "Not tested yet.": (False, False),
               "Behoben, alle Tests bestanden.": (False, False)},
    "negated": {"doğrulanmadı": True, "not verified": True,
                "nicht verifiziert": False},
    "blocker": {"KARAR: hangi yol": True, "DECISION: which path": True,
                "KARAR gerekmiyor": False, "ENTSCHEIDUNG: welcher Weg": False},
    "prompts": {"make the settings page look better": {"spec"},
                "ayarlar sayfasını daha güzel göster": {"product"},
                "research which retry library is best and compare them": {"research"},
                "araştır hangi retry kütüphanesi en iyi, karşılaştır": {"research"},
                "who calls parse_config": {"graph"},
                "parse_config kim çağırıyor": {"graph"},
                "lass die Einstellungsseite besser aussehen": set(),
                "wer ruft parse_config auf": set()},
    "needles": {"don't touch hooks.json": ["hooks.json"],
                "hooks.json'a dokunma": ["hooks.json"],
                "bana sormadan push etme": ["push"],
                "ask me before pushing": ["pushing"],
                "fass hooks.json nicht an": []},
}
# The S5 probe's reply-language paragraphs (scripts/s5/probe.py).
PROSE = {
    "tr": "Ayrıştırıcı artık yapılandırma dosyasını okuyor ve testler yeni dalı "
          "kapsıyor. Yükleyiciyi boş satırları atlayacak şekilde değiştirdim ve iki "
          "başarısız durum bu değişiklikten sonra geçiyor. Sürüm notları yeni "
          "bayrağı ve varsayılan değeri anlatıyor.",
    "es": "El analizador ahora lee el archivo de configuración y las pruebas cubren "
          "la nueva rama. Cambié el cargador para que omita las líneas vacías, y los "
          "dos casos que fallaban pasan después del cambio. Las notas de la versión "
          "describen la nueva opción y el valor por defecto en el archivo de la "
          "aplicación.",
    "fr": "Le analyseur lit maintenant le fichier de configuration et les tests "
          "couvrent la nouvelle branche. Je ai modifié le chargeur pour ignorer les "
          "lignes vides, et les deux cas en échec passent après le changement. Les "
          "notes de version décrivent la nouvelle option et la valeur par défaut de "
          "la application.",
    "nl": "De parser leest nu het configuratiebestand en de tests dekken de nieuwe "
          "tak. Ik heb de lader aangepast zodat hij lege regels overslaat, en de twee "
          "falende gevallen slagen na de wijziging. De release notes beschrijven de "
          "nieuwe vlag en de standaardwaarde en de werking van de app.",
}

PROBE = r"""
import json, sys
import tezgah_integrity as ti, tezgah_context as tc
print(json.dumps({
    "residual": ti._residual("Offene Punkte"),
    "sycophant": bool(ti.SYCOPHANT.search("Du hast recht, ich habe es behoben.")),
    "negated": bool(ti.NEGATED.search("nicht verifiziert")),
    "blocker": bool(ti.BLOCKER_SAID.search("ENTSCHEIDUNG: welcher Weg")),
    "research": sorted(tc.classify_prompt(
        "recherchiere welche Retry-Bibliothek am besten ist und vergleiche sie")),
    "graph": sorted(tc.classify_prompt("wer ruft parse_config auf")),
    "english": ti._residual("Open items"),
}))
"""


class PackParity(unittest.TestCase):
    def test_every_pack_answers_every_class_in_one_shape(self):
        codes = sorted(f[:-5] for f in os.listdir(LANG_DIR) if f.endswith(".json"))
        self.assertEqual(codes, ["en", "tr"])
        en = shape(load("en"))
        for code in codes:
            self.assertEqual(shape(load(code)), en, code)


class NoRegression(unittest.TestCase):
    def test_the_probe_answers_what_the_inlined_regexes_did(self):
        got = {
            "residual": {s: ti._residual(s) for s in GOLDEN["residual"]},
            "sycophant": {s: bool(ti.SYCOPHANT.search(s)) for s in GOLDEN["sycophant"]},
            "closer": {s: bool(ti.CLOSER.search(s)) for s in GOLDEN["closer"]},
            "claims": {s: tuple(ti.asserted_claims(s)) for s in GOLDEN["claims"]},
            "negated": {s: bool(ti.NEGATED.search(s)) for s in GOLDEN["negated"]},
            "blocker": {s: bool(ti.BLOCKER_SAID.search(s)) for s in GOLDEN["blocker"]},
            "prompts": {s: tc.classify_prompt(s) for s in GOLDEN["prompts"]},
            "needles": {s: [tc.constraint_needle(c) for c in tc.user_constraints(s)]
                        for s in GOLDEN["needles"]},
        }
        self.assertEqual(got, GOLDEN)


class ReplyMarkers(unittest.TestCase):
    def test_spanish_french_and_dutch_prose_is_not_read_as_turkish(self):
        shares = {k: ti.reply_share(ti.prose_words(v)) for k, v in PROSE.items()}
        self.assertGreaterEqual(shares.pop("tr"), ti.LANG_MIN_SHARE)
        for code, share in shares.items():
            self.assertLess(share, ti.LANG_MIN_SHARE, code)

    def test_english_ships_no_markers_so_no_reply_is_held_to_it(self):
        self.assertIsNone(ti.reply_share(ti.prose_words(PROSE["tr"]), "en"))


class OneFileAddsALanguage(unittest.TestCase):
    def test_a_german_pack_arms_the_german_rows(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        hooks = shutil.copytree(support.HOOKS, os.path.join(tmp, "hooks"),
                                ignore=shutil.ignore_patterns("__pycache__"))
        de = copy.deepcopy(load("en"))
        de.update(name="German", residual_label=[r"offene punkte"],
                  negated=[r"nicht verifiziert"])
        de["sycophant"]["opener"] = [r"du hast recht"]
        de["blockers"]["decision"]["pattern"] = "ENTSCHEIDUNG"
        de["hints"]["research"] = [r"recherchier\w*|vergleich\w*"]
        de["hints"]["graph"] = [r"wer ruft"]
        with open(os.path.join(hooks, "lang", "de.json"), "w", encoding="utf-8") as fh:
            json.dump(de, fh, ensure_ascii=False)

        def probe(path):
            out = subprocess.run([sys.executable, "-c", PROBE], capture_output=True,
                                 text=True, cwd=tmp, timeout=60,
                                 env=support.base_env(tmp, extra={"PYTHONPATH": path}))
            self.assertEqual(out.returncode, 0, out.stderr)
            return json.loads(out.stdout)

        self.assertEqual(probe(hooks), {
            "residual": True, "sycophant": True, "negated": True, "blocker": True,
            "research": ["research"], "graph": ["graph"], "english": True})
        self.assertEqual(probe(support.HOOKS), {
            "residual": False, "sycophant": False, "negated": False, "blocker": False,
            "research": [], "graph": [], "english": True})


if __name__ == "__main__":
    unittest.main()
