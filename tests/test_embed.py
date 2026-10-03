"""hooks/tezgah_embed.py: the opt-in embedding fusion, its file, and its fetch.

Every model here is generated in the test from a handful of hand-made vectors:
no download, no network. The conversion is the one `tezgah-setup --enable` runs,
so a golden ranking read back through the reader pins the recipe (the head cut,
the base-vocabulary cut, the PCA) as well as the reader.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import math
import os
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

import support

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_embed as te  # noqa: E402
import tezgah_paths as tp  # noqa: E402
import tezgah_rank  # noqa: E402

# Source dims 3, kept dims 2: the third dim points "blue sky" at "red", so a
# converter that kept it would rank "blue sky" first for "red".
WORDPIECE = [("[PAD]", (0, 0, 0)), ("[UNK]", (0, 0, 0)), ("red", (1, 0, 5)),
             ("apple", (0.9, 0.1, -5)), ("fruit", (0.2, 1.0, 0)),
             ("blue", (-1, 0, 5)), ("sky", (-0.9, 0.2, 0)), ("car", (0, -1, 0)),
             ("##s", (0, 0, 0))]
TEXTS = ["blue sky", "red apples", "fruit", "car"]


def _safetensors(path, name, rows):
    data = b"".join(struct.pack("<%df" % len(r), *r) for r in rows)
    header = json.dumps({name: {"dtype": "F32", "shape": [len(rows), len(rows[0])],
                                "data_offsets": [0, len(data)]}}).encode()
    with open(path, "wb") as fh:
        fh.write(struct.pack("<Q", len(header)) + header + data)


def _wordpiece_sources(d):
    _safetensors(os.path.join(d, "model"), "embedding.weight", [v for _t, v in WORDPIECE])
    tok = {"normalizer": {"type": "BertNormalizer", "lowercase": True, "strip_accents": None},
           "model": {"type": "WordPiece", "unk_token": "[UNK]",
                     "continuing_subword_prefix": "##", "max_input_chars_per_word": 100,
                     "vocab": {t: i for i, (t, _v) in enumerate(WORDPIECE)}}}
    with open(os.path.join(d, "tokenizer"), "w", encoding="utf-8") as fh:
        json.dump(tok, fh)


# Unigram, source dims 4: every kept row lies in the plane of U1 and U2, so a
# 2-axis PCA keeps every cosine. The last two pieces share the minimum score -
# the tail a base-vocabulary cut drops - and point far out of that plane; had
# they reached the PCA, an axis would follow them and the cosines would move.
U1 = (1 / math.sqrt(2), 1 / math.sqrt(2), 0.0, 0.0)
U2 = (0.0, 0.0, 1 / math.sqrt(2), -1 / math.sqrt(2))
PLANE = {"\u2581red": (1.0, 0.0), "\u2581apple": (0.9, 0.2), "\u2581fruit": (0.1, 1.0),
         "\u2581blue": (-1.0, 0.1), "\u2581sky": (-0.8, 0.3), "\u2581car": (0.0, -1.0)}


def _plane(a, b):
    return tuple(a * x + b * y for x, y in zip(U1, U2))


def _unigram_sources(d):
    pieces = [["[PAD]", 0.0], ["[UNK]", 0.0]] + [[p, -1.0] for p in PLANE] \
        + [["\u2581zz", -9.0], ["\u2581qq", -9.0]]
    rows = [(0.0,) * 4, (0.0,) * 4] + [_plane(*v) for v in PLANE.values()] \
        + [(0.0, 90.0, 0.0, 0.0), (0.0, 0.0, 90.0, 90.0)]
    _safetensors(os.path.join(d, "model"), "embeddings", rows)
    tok = {"normalizer": {"type": "Sequence", "normalizers": []},
           "model": {"type": "Unigram", "unk_id": 1, "vocab": pieces}}
    with open(os.path.join(d, "tokenizer"), "w", encoding="utf-8") as fh:
        json.dump(tok, fh)


def _spec(mode, vocab, sha="0" * 64):
    return {"repo": "test/tiny", "revision": "0" * 40, "license": "MIT",
            "files": {"model": ("model", ""), "tokenizer": ("tokenizer", "")},
            "dims": 2, "dims_mode": mode, "vocab": vocab, "sha256": sha}


def _by_cosine(reader, query, texts):
    q = reader.embed(query)
    sims = [te.cosine(q, reader.embed(t)) for t in texts]
    return sorted(range(len(texts)), key=lambda i: (-sims[i], i))


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.src = os.path.join(self.dir, "src")
        os.mkdir(self.src)
        te._LOADED.clear()
        self.addCleanup(te._LOADED.clear)
        for patch in (mock.patch.object(tp, "CACHE", os.path.join(self.dir, "cache")),
                      mock.patch.object(tp, "CONFIG", os.path.join(self.dir, "config.json"))):
            patch.start()
            self.addCleanup(patch.stop)

    def build(self, sources, spec):
        sources(self.src)
        out = os.path.join(self.dir, "built.bin")
        te.convert(spec, os.path.join(self.src, "model"),
                   os.path.join(self.src, "tokenizer"), out)
        return out

    def install(self, sources, spec, select=True):
        """The built file as the `embed-mrl` model, pinned to its own sha256."""
        path = self.build(sources, spec)
        sha = te._sha256(path)
        os.makedirs(os.path.dirname(te.model_path("embed-mrl")))
        shutil.copy(path, te.model_path("embed-mrl"))
        patch = mock.patch.dict(te.MODELS, {"embed-mrl": dict(spec, sha256=sha)})
        patch.start()
        self.addCleanup(patch.stop)
        if select:
            self.select(["embed-mrl"])
        return te.model_path("embed-mrl")

    def select(self, ids):
        with open(tp.CONFIG, "w", encoding="utf-8") as fh:
            json.dump({"features": ids}, fh)


class Reader(Case):
    def test_the_wordpiece_head_cut_reproduces_the_golden_ranking(self):
        reader = te.Reader(self.build(_wordpiece_sources, _spec("head", "all")))
        self.assertEqual(reader.dim, 2)
        # "apples" is apple + ##s, "Red" is lowercased
        self.assertEqual(reader.tokenize("Red apples"), [2, 3, 8])
        self.assertEqual(_by_cosine(reader, "red", TEXTS), [1, 2, 3, 0])

    def test_the_pca_keeps_every_cosine_of_a_planar_table(self):
        path = self.build(_unigram_sources, _spec("pca", "base"))
        reader = te.Reader(path)
        with open(path, "rb") as fh:
            fh.seek(len(te.MAGIC))
            size = struct.unpack("<Q", fh.read(8))[0]
            self.assertEqual(json.loads(fh.read(size))["rows"], 2 + len(PLANE))
        words = [p[1:] for p in PLANE]
        for a in words:
            for b in words:
                want = sum(x * y for x, y in zip(PLANE["\u2581" + a], PLANE["\u2581" + b])) \
                    / math.hypot(*PLANE["\u2581" + a]) / math.hypot(*PLANE["\u2581" + b])
                self.assertAlmostEqual(te.cosine(reader.embed(a), reader.embed(b)), want,
                                       delta=0.02, msg=(a, b))
        self.assertEqual(_by_cosine(reader, "red", ["blue sky", "red apple", "fruit", "car"]),
                         [1, 2, 3, 0])


class Fuse(Case):
    QUERIES = ("red", "reds", "blue fruit", "zzz")

    def assert_bm25(self):
        for q in self.QUERIES:
            self.assertEqual(te.fuse(q, TEXTS, 3), tezgah_rank.rank(q, TEXTS, 3), q)

    def test_the_feature_on_fuses_the_two_rankings(self):
        self.install(_wordpiece_sources, _spec("head", "all"))
        self.assertEqual(te.fuse("red", TEXTS, 4), [1, 2, 3, 0])
        # no shared word: BM25 places nothing, the embedding still finds it
        self.assertEqual(tezgah_rank.rank("reds", TEXTS, 4), [])
        self.assertEqual(te.fuse("reds", TEXTS, 2), [1, 2])

    def test_the_feature_off_is_bm25_even_with_the_file_in_place(self):
        self.install(_wordpiece_sources, _spec("head", "all"), select=False)
        self.assert_bm25()
        self.select(["mcp-playwright"])
        self.assert_bm25()

    def test_a_missing_file_is_bm25(self):
        self.select(["embed-mrl"])
        self.assertFalse(os.path.exists(te.model_path("embed-mrl")))
        self.assert_bm25()

    def test_a_corrupt_file_is_bm25(self):
        path = self.install(_wordpiece_sources, _spec("head", "all"))
        with open(path, "r+b") as fh:
            fh.seek(-1, os.SEEK_END)
            last = fh.read(1)
            fh.seek(-1, os.SEEK_END)
            fh.write(bytes([last[0] ^ 1]))
        self.assertIsNone(te.valid("embed-mrl"))
        self.assert_bm25()

    def test_an_unreadable_file_with_the_pinned_sha_is_bm25(self):
        self.install(_wordpiece_sources, _spec("head", "all"))
        with open(te.model_path("embed-mrl"), "wb") as fh:
            fh.write(b"not a model")
        te.MODELS["embed-mrl"]["sha256"] = hashlib.sha256(b"not a model").hexdigest()
        self.assertEqual(te.valid("embed-mrl"), te.model_path("embed-mrl"))
        self.assert_bm25()


class Fetch(Case):
    def stub(self, payloads):
        """A downloader that serves the test's files instead of the network."""
        def get(url, dest):
            self.urls.append(url)
            with open(dest, "wb") as fh:
                fh.write(payloads[url.rsplit("/", 1)[1]])
            return hashlib.sha256(payloads[url.rsplit("/", 1)[1]]).hexdigest()
        self.urls = []
        return get

    def sources(self):
        _wordpiece_sources(self.src)
        out = {}
        for n in ("model", "tokenizer"):
            with open(os.path.join(self.src, n), "rb") as fh:
                out[n] = fh.read()
        return out

    def spec(self, payloads, produced):
        spec = _spec("head", "all", produced)
        spec["files"] = {r: (r, hashlib.sha256(b).hexdigest()) for r, b in payloads.items()}
        return spec

    def pinned(self, payloads, produced):
        return mock.patch.dict(te.MODELS, {"embed-mrl": self.spec(payloads, produced)})

    def assert_nothing_left(self):
        self.assertFalse(os.path.exists(te.model_path("embed-mrl")))
        self.assertEqual(os.listdir(os.path.dirname(te.model_path("embed-mrl"))), [])

    def test_a_verified_fetch_installs_an_owner_only_file(self):
        payloads = self.sources()
        # the header records the source pins, so the expected file is built
        # from the same spec the fetch reads
        produced = te._sha256(self.build(_wordpiece_sources, self.spec(payloads, "")))
        with self.pinned(payloads, produced):
            path = te.fetch("embed-mrl", get=self.stub(payloads))
            self.assertEqual(te.valid("embed-mrl"), path)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertTrue(all(u.startswith("https://huggingface.co/test/tiny/resolve/")
                            for u in self.urls), self.urls)

    def test_a_source_sha_mismatch_is_refused(self):
        payloads = self.sources()
        with self.pinned(payloads, "0" * 64):
            payloads["tokenizer"] += b" "
            with self.assertRaisesRegex(ValueError, "pinned"):
                te.fetch("embed-mrl", get=self.stub(payloads))
        self.assert_nothing_left()

    def test_a_converted_file_off_its_pin_is_refused(self):
        payloads = self.sources()
        with self.pinned(payloads, "0" * 64):
            with self.assertRaisesRegex(ValueError, "converted file"):
                te.fetch("embed-mrl", get=self.stub(payloads))
        self.assert_nothing_left()

    def test_remove_takes_the_file(self):
        self.install(_wordpiece_sources, _spec("head", "all"))
        self.assertTrue(te.remove("embed-mrl"))
        self.assertFalse(te.remove("embed-mrl"))
        self.assertIsNone(te.valid("embed-mrl"))

    def test_a_killed_fetchs_work_dir_is_swept(self):
        # SIGKILL skips fetch()'s `finally`, leaving ~0.5 GB in a .fetch-* dir
        home = os.path.dirname(te.model_path("embed-mrl"))
        outside = os.path.join(self.dir, "outside")
        os.makedirs(outside)
        os.makedirs(home)
        for name in ("keep", ".fetch-file"):
            open(os.path.join(home, name), "w").close()
        open(os.path.join(outside, "model"), "w").close()
        os.symlink(outside, os.path.join(home, ".fetch-link"))

        def leftover():
            os.makedirs(os.path.join(home, ".fetch-x"))
            open(os.path.join(home, ".fetch-x", "model"), "w").close()

        def assert_swept():
            self.assertFalse(os.path.exists(os.path.join(home, ".fetch-x")))
            for name in ("keep", ".fetch-file", ".fetch-link"):
                self.assertTrue(os.path.lexists(os.path.join(home, name)), name)
            self.assertTrue(os.path.exists(os.path.join(outside, "model")))

        leftover()
        te.remove("embed-mrl")
        assert_swept()
        leftover()
        payloads = self.sources()
        produced = te._sha256(self.build(_wordpiece_sources, self.spec(payloads, "")))
        with self.pinned(payloads, produced):
            te.fetch("embed-mrl", get=self.stub(payloads))
        assert_swept()


class DocsRanked(Case):
    def test_an_empty_phrasing_gives_a_page_no_cosine_floor(self):
        cli = os.path.join(support.REPO, "bin", "tezgah-docs")
        loader = importlib.machinery.SourceFileLoader("tezgah_docs_embed", cli)
        docs = importlib.util.module_from_spec(
            importlib.util.spec_from_loader("tezgah_docs_embed", loader))
        loader.exec_module(docs)
        # "blue" is the farthest from "red"; its page's empty title_tr would
        # embed as the zero vector and lift it to a cosine of 0.0 over "sky"
        pages = [{"path": "a.md", "title": "blue", "title_tr": "", "answers": []},
                 {"path": "b.md", "title": "sky", "title_tr": "sky", "answers": []}]
        self.install(_wordpiece_sources, _spec("head", "all"))
        with mock.patch.object(docs, "entries", return_value=pages):
            self.assertEqual([p["path"] for p in docs.ranked("red")], ["b.md", "a.md"])


if __name__ == "__main__":
    unittest.main()
