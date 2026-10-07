"""Opt-in static embeddings beside BM25: which of a few short texts a query is about.

`tezgah_rank` matches words, so a Turkish question meets an English page only
through the phrasings `docs/index.json` carries, and a lesson worded differently
from the prompt is missed. A static embedding model (one vector per token,
mean-pooled - no network, no third-party package) ranks by meaning. The two
callers use it differently, each the way it measured best: the lessons block
keeps BM25's order and adds a line by meaning only above the model's cosine
`floor` (`fuse`), and the docs fallback ranks pages by meaning alone (`nearest`).

Off by default. `tezgah-setup --enable embed-mrl` (or `embed-m2v`) runs
`fetch()` once: the pinned source files over HTTPS, a stdlib conversion into one
compact file under the tezgah cache, and a sha256 check of both ends. At hook
time the file is read only when the feature is selected and the file is the
pinned one (`valid`); any other state, or any error, is BM25 exactly as
`tezgah_rank.rank` answers it. Nothing here downloads outside `fetch()`.

Measured (an internal research line, 200 real prompts over a 46-line
ledger, two blind raters): reciprocal-rank fusion gave every prompt three
lessons, 94% of them irrelevant. BM25 first plus the floor gives a no-topic
prompt a lesson 0.17 of the time (BM25 alone 0.10-0.14) at a recall@3 at most
0.02 above BM25's, for the price of loading the model on every prompt. On
held-out Turkish docs phrasings cosine alone found the page in the top 3 for 0.91
(embed-mrl) against the fusion's 0.75.

The file: MAGIC, a little-endian u64 header length, the header (JSON: the
tokenizer and the source pins), then `rows` records of a float32 scale followed
by `dim` int8 values. Rows are read with os.pread, only for the tokens a text
uses.
"""
import array
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import unicodedata

import tezgah_paths as tp
import tezgah_rank

MAGIC = b"TZEMB1\n\0"
URL = "https://huggingface.co/%s/resolve/%s/%s"
LITTLE = sys.byteorder == "little"

# Pinned by repository, commit and sha256 of every source file and of the file
# the conversion produces, so `fetch()` either writes exactly the measured table
# or nothing. The recipes are the research exports: V5-mrl keeps the first 128
# of 1024 Matryoshka dims; V5-m2v drops the vocabulary tail Tokenlearn appended
# and projects onto the top 128 uncentered principal axes. `floor` is the cosine
# a lesson BM25 missed must reach (`fuse`), chosen per model on half of the
# relevance-measurement prompts (the smallest that gave a lesson to at most 30% of
# the no-topic prompts) and quoted from the other half.
MODELS = {
    "embed-mrl": {
        "repo": "sentence-transformers/static-similarity-mrl-multilingual-v1",
        "revision": "b68f4122911bcffcd6e1f695f2d99cd6788972d8",
        "license": "Apache-2.0",
        "files": {
            "model": ("0_StaticEmbedding/model.safetensors",
                      "8245ab78ee71dded845a82d2270fcb9e785b29dad0e1619f69d5390c47d9ba00"),
            "tokenizer": ("0_StaticEmbedding/tokenizer.json",
                          "11aaf894a4ccf3d95e8830e27c0f8152791fbbff2b988e29a265580b86edd216")},
        "dims": 128, "dims_mode": "head", "vocab": "all", "floor": 0.30,
        "sha256": "6f67d97229db9eda0dad4da677329f93ecd7ebc7b1b7195138cd215f676a19f2"},
    "embed-m2v": {
        "repo": "minishlab/potion-multilingual-128M",
        "revision": "73908c3438cf03b6a01bcb9611d62b23d0726f08",
        "license": "MIT",
        "files": {
            "model": ("model.safetensors",
                      "14b5eb39cb4ce5666da8ad1f3dc6be4346e9b2d601c073302fa0a31bf7943397"),
            "tokenizer": ("tokenizer.json",
                          "19f1909063da3cfe3bd83a782381f040dccea475f4816de11116444a73e1b6a1")},
        "dims": 128, "dims_mode": "pca", "vocab": "base", "floor": 0.50,
        "sha256": "6673b36dae49ca42f15a82ea0724570807c9a6d80fa31cafa9fb89ee78d3fd09"},
}


# --- the reader -------------------------------------------------------------
# Ported from the research reader (token ids identical to model2vec 0.9.0 on
# 244 texts, top-5 identical on 32 queries, same output under Python 3.10 -I -S).

def _is_punct(ch):
    cp = ord(ch)
    if 33 <= cp <= 47 or 58 <= cp <= 64 or 91 <= cp <= 96 or 123 <= cp <= 126:
        return True
    return unicodedata.category(ch).startswith("P")


def _is_cjk(cp):
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF
            or 0x2A700 <= cp <= 0x2B73F or 0x2B740 <= cp <= 0x2B81F or 0x2B820 <= cp <= 0x2CEAF
            or 0xF900 <= cp <= 0xFAFF or 0x2F800 <= cp <= 0x2FA1F)


class WordPiece:
    """BERT normalizer (clean, CJK, strip accents, lowercase) + BertPreTokenizer + WordPiece."""

    def __init__(self, tokens, meta):
        self.ids = {t: i for i, t in enumerate(tokens)}
        self.unk = self.ids.get(meta.get("unk_token", "[UNK]"))
        self.lower = meta.get("lowercase", True)
        self.strip = meta.get("strip_accents")
        if self.strip is None:
            self.strip = self.lower
        self.prefix = meta.get("prefix", "##")
        self.max_chars = meta.get("max_input_chars_per_word", 100)

    def normalize(self, text):
        out = []
        for ch in text:
            cp = ord(ch)
            if cp == 0 or cp == 0xFFFD:
                continue
            cat = unicodedata.category(ch)
            if ch in "\t\n\r" or cat == "Zs" or ch.isspace():
                out.append(" ")
                continue
            if cat in ("Cc", "Cf"):
                continue
            if _is_cjk(cp):
                out.append(" " + ch + " ")
                continue
            out.append(ch)
        text = "".join(out)
        if self.strip:
            text = "".join(c for c in unicodedata.normalize("NFD", text)
                           if unicodedata.category(c) != "Mn")
        if self.lower:
            text = text.lower()
        return text

    def words(self, text):
        words, cur = [], []
        for ch in text:
            if ch.isspace():
                if cur:
                    words.append("".join(cur))
                    cur = []
            elif _is_punct(ch):
                if cur:
                    words.append("".join(cur))
                    cur = []
                words.append(ch)
            else:
                cur.append(ch)
        if cur:
            words.append("".join(cur))
        return words

    def encode(self, text):
        ids = []
        for word in self.words(self.normalize(text)):
            if len(word) > self.max_chars:
                ids.append(self.unk)
                continue
            start, pieces = 0, []
            while start < len(word):
                end, found = len(word), None
                while start < end:
                    sub = word[start:end]
                    if start > 0:
                        sub = self.prefix + sub
                    if sub in self.ids:
                        found = self.ids[sub]
                        break
                    end -= 1
                if found is None:
                    pieces = [self.unk]
                    break
                pieces.append(found)
                start = end
            ids.extend(pieces)
        return ids


class Unigram:
    """SentencePiece-style Unigram (XLM-R): NFKC (stands in for the precompiled
    charsmap), the export's string replacements, Metaspace, Viterbi."""

    def __init__(self, pieces, scores, meta):
        self.ids = {p: i for i, p in enumerate(pieces)}
        self.scores = scores
        self.unk = meta.get("unk_id", 1)
        for special in meta.get("skip_pieces", []):
            self.ids.pop(special, None)
        self.maxlen = max(len(p) for p in self.ids)
        self.unk_score = min(scores) - 10.0
        self.ops = [(op[0], re.compile(op[1]), op[2]) if op[0] == "re" else tuple(op)
                    for op in meta.get("replacements", [])]

    def normalize(self, text):
        for op in self.ops:
            if op[0] == "nfkc":
                text = unicodedata.normalize("NFKC", text)
            elif op[0] == "str":
                text = text.replace(op[1], op[2])
            elif op[0] == "re":
                text = op[1].sub(op[2], text)
            elif op[0] == "strip":
                text = text.lstrip() if op[1] else text
                text = text.rstrip() if op[2] else text
        text = text.replace(" ", "\u2581")
        if not text.startswith("\u2581"):
            text = "\u2581" + text
        return text

    def encode(self, text):
        s = self.normalize(text)
        n = len(s)
        best = [None] * (n + 1)
        back = [None] * (n + 1)
        best[0] = 0.0
        ids, scores, maxlen = self.ids, self.scores, self.maxlen
        for pos in range(n):
            base = best[pos]
            if base is None:
                continue
            single = False
            for length in range(1, min(maxlen, n - pos) + 1):
                pid = ids.get(s[pos:pos + length])
                if pid is None:
                    continue
                if length == 1:
                    single = True
                cand = base + scores[pid]
                end = pos + length
                if best[end] is None or cand > best[end]:
                    best[end] = cand
                    back[end] = (pos, pid)
            if not single:
                cand = base + self.unk_score
                if best[pos + 1] is None or cand > best[pos + 1]:
                    best[pos + 1] = cand
                    back[pos + 1] = (pos, self.unk)
        out, end = [], n
        while end > 0:
            pos, pid = back[end]
            out.append(pid)
            end = pos
        out.reverse()
        return out


class Reader:
    """One model file: tokenize, look up int8 rows, mean-pool, normalise."""

    def __init__(self, path):
        with open(path, "rb") as fh:
            if fh.read(len(MAGIC)) != MAGIC:
                raise ValueError("%s: not a tezgah embedding file" % path)
            size = struct.unpack("<Q", fh.read(8))[0]
            meta = json.loads(fh.read(size).decode("utf-8"))
        self.base = len(MAGIC) + 8 + size
        self.dim = meta["dim"]
        self.row_bytes = 4 + self.dim
        if os.path.getsize(path) != self.base + meta["rows"] * self.row_bytes:
            raise ValueError("%s: size does not match its header" % path)
        if meta["tokenizer"] == "wordpiece":
            self.tok = WordPiece(meta["vocab"], meta)
        else:
            self.tok = Unigram([p for p, _s in meta["pieces"]],
                               [s for _p, s in meta["pieces"]], meta)
        self.unk = meta.get("unk_id")
        self.fd = os.open(path, os.O_RDONLY)
        self.cache = {}

    def row(self, i):
        vec = self.cache.get(i)
        if vec is None:
            raw = os.pread(self.fd, self.row_bytes, self.base + i * self.row_bytes)
            scale = struct.unpack("<f", raw[:4])[0]
            vec = self.cache[i] = [x * scale for x in array.array("b", raw[4:])]
        return vec

    def tokenize(self, text):
        return [i for i in self.tok.encode(text) if i != self.unk]

    def embed(self, text):
        acc = [0.0] * self.dim
        for i in self.tokenize(text):
            for k, v in enumerate(self.row(i)):
                acc[k] += v
        norm = math.sqrt(sum(v * v for v in acc))
        return [v / norm for v in acc] if norm else acc


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


# --- the hook-time half -----------------------------------------------------

def model_path(ident):
    return os.path.join(tp.CACHE, "embed", ident + ".bin")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def valid(ident):
    """The model file's path when it is the pinned one, else None. A pure read:
    the `--features` probe and every hook-time load ask this."""
    path = model_path(ident)
    try:
        return path if _sha256(path) == MODELS[ident]["sha256"] else None
    except (OSError, KeyError):
        return None


_LOADED = {}


def reader():
    """The selected model's Reader, carrying its `floor`, or None: not selected,
    not fetched, not the pinned file, or anything at all that raised."""
    try:
        import tezgah_apps
        for ident in tezgah_apps.selected_ids(tp.config().get("features")):
            path = valid(ident) if ident in MODELS else None
            if path:
                if path not in _LOADED:
                    _LOADED[path] = Reader(path)
                    _LOADED[path].floor = MODELS[ident].get("floor")
                return _LOADED[path]
    except Exception:  # fail-open: the caller ranks by words alone
        return None
    return None


def _cosines(model, query, texts, groups):
    """Each text's best cosine to `query` over its `groups` strings (default:
    the text itself), or None when the query has no token the model knows."""
    q = model.embed(query)
    if not any(q):
        return None
    return [max((cosine(q, model.embed(t)) for t in g), default=-1.0)
            for g in (groups or [[t] for t in texts])]


def fuse(query, texts, k, groups=None, max_df=None):
    """Indices of the `k` texts most about `query`, best first: the lessons ranking.

    BM25's own order first - with no usable model this is exactly
    `tezgah_rank.rank(query, texts, k, max_df)`, `max_df` being the lessons
    path's cap - then the texts BM25 missed, by cosine, each only when it reaches
    the model's `floor` (a model with none fills unconditionally), so a prompt
    about nothing gets nothing."""
    words = tezgah_rank.rank(query, texts, len(texts), max_df)
    model = reader()
    if model is None:
        return words[:k]
    try:
        sims = _cosines(model, query, texts, groups)
        if sims is None:
            return words[:k]
        hits, floor = set(words), model.floor
        more = sorted((i for i in range(len(texts)) if i not in hits
                       and (floor is None or sims[i] >= floor)),
                      key=lambda i: (-sims[i], i))
        return (words + more)[:k]
    except Exception:  # fail-open
        return words[:k]


def nearest(query, texts, k, groups=None):
    """Indices of the `k` texts nearest `query` by cosine alone, best first: the
    docs ranking, where BM25's matches on Turkish function words outvoted the
    meaning. With no usable model, `tezgah_rank.rank(query, texts, k)` exactly."""
    model = reader()
    if model is not None:
        try:
            sims = _cosines(model, query, texts, groups)
            if sims is not None:
                return sorted(range(len(texts)), key=lambda i: (-sims[i], i))[:k]
        except Exception:  # fail-open
            pass
    return tezgah_rank.rank(query, texts, k)


# --- the setup-time half: fetch, convert, verify ----------------------------
# Runs from `tezgah-setup --enable`, never from a hook. Every value is
# reproducible bit for bit on any Python >= 3.10: the int8 rounding emulates the
# float32 arithmetic of the research export, and the PCA is exact integer
# arithmetic (Gram matrix, projection) around a cyclic Jacobi eigensolver that
# uses only + - * / and sqrt.

class _Progress:
    """One status line for a long setup step: rewritten in place on a terminal,
    one line per 10% otherwise (a log keeps a readable trail, not 400 updates)."""

    def __init__(self, label, total, unit="", scale=1):
        self.label, self.total, self.unit, self.scale = label, total, unit, scale
        self.done, self.step = 0, -1
        self.tty = sys.stdout.isatty()

    def __call__(self, n=1):
        self.done += n
        shown = "%d" % (self.done // self.scale)
        if self.total:
            pct = min(100, self.done * 100 // self.total)
            shown += "/%d%s  %d%%" % (self.total // self.scale, self.unit, pct)
            if not self.tty and pct // 10 == self.step:
                return
            self.step = pct // 10
        else:
            shown += self.unit
            if not self.tty:
                return
        sys.stdout.write(("\r    %s  %s" if self.tty else "    %s  %s\n") % (self.label, shown))
        sys.stdout.flush()

    def close(self):
        if self.tty:
            sys.stdout.write("\n")
            sys.stdout.flush()


def _download(url, dest):
    """Stream `url` into `dest`; returns the sha256 of what was written."""
    import urllib.request
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        tick = _Progress("downloaded", total, " MB", 1 << 20)
        for block in iter(lambda: resp.read(1 << 20), b""):
            h.update(block)
            out.write(block)
            tick(len(block))
        tick.close()
    return h.hexdigest()


def _tensor(path):
    """(data offset, rows, cols) of the one float32 embedding table in a
    safetensors file."""
    with open(path, "rb") as fh:
        size = struct.unpack("<Q", fh.read(8))[0]
        header = json.loads(fh.read(size).decode("utf-8"))
    name = "embeddings" if "embeddings" in header else "embedding.weight"
    t = header[name]
    if t["dtype"] != "F32" or len(t["shape"]) != 2:
        raise ValueError("%s: %s is %s %s, not a float32 matrix"
                         % (path, name, t["dtype"], t["shape"]))
    return 8 + size + t["data_offsets"][0], t["shape"][0], t["shape"][1]


def _rows(job):
    """The float32 rows [start, stop) of the table in job as arrays."""
    path, base, cols, start, stop = job[:5]
    stride = 4 * cols
    fd = os.open(path, os.O_RDONLY)
    try:
        raw = os.pread(fd, (stop - start) * stride, base + start * stride)
    finally:
        os.close(fd)
    for r in range(stop - start):
        a = array.array("f", raw[r * stride:(r + 1) * stride])
        if not LITTLE:
            a.byteswap()
        yield a


def _quantise(values):
    """One row as a float32 scale + int8 values, rounded exactly as numpy does
    it in float32: scale = max|x| / 127, q = clip(rint(x / scale), -127, 127)."""
    v = array.array("f", values)
    scale = array.array("f", [max(map(abs, v), default=0.0) / 127.0])[0] or 1.0
    q = array.array("f", [x / scale for x in v])
    return struct.pack("<f", scale) + array.array(
        "b", [max(-127, min(127, round(x))) for x in q]).tobytes()


# Signed integers packed 64 bits apart into one Python int, so one big-int
# multiply-add does a whole row of fixed-point products in C.
_B62, _B63 = 1 << 62, 1 << 63


def _offset(n, bias):
    return sum(bias << (64 * j) for j in range(n))


def _pack(ints):
    n = len(ints)
    return (int.from_bytes(struct.pack("<%dQ" % n, *[v + _B62 for v in ints]), "little")
            - _offset(n, _B62))


def _unpack(big, n):
    raw = (big + _offset(n, _B63)).to_bytes(8 * n, "little")
    return [f - _B63 for f in struct.unpack("<%dQ" % n, raw)]


def _absmax_part(job):
    return max((max(map(abs, row)) for row in _rows(job)), default=0.0)


def _gram_part(job):
    """sum(row^T row) over the job's rows, the row scaled by 2**shift to
    integers below 2**20: each of the cols accumulators packs one Gram row."""
    shift = job[5]
    acc = [0] * job[2]
    for row in _rows(job):
        ints = [round(math.ldexp(x, shift)) for x in row]
        packed = _pack(ints)
        for i, v in enumerate(ints):
            if v:
                acc[i] += v * packed
    return acc


def _head_part(job):
    dims = job[5]
    return b"".join(_quantise(row[:dims]) for row in _rows(job))


def _pca_part(job):
    """Each row projected onto the packed axes (fixed point: the row below
    2**20, the axes at 2**30), then quantised."""
    axes, dims = job[5], job[6]
    out = []
    for row in _rows(job):
        top = max(map(abs, row), default=0.0)
        if not top:
            out.append(_quantise([0.0] * dims))
            continue
        shift = 20 - math.frexp(top)[1]
        acc = 0
        for x, w in zip(row, axes):
            if x:
                acc += round(math.ldexp(x, shift)) * w
        out.append(_quantise([math.ldexp(v, -(shift + 30)) for v in _unpack(acc, dims)]))
    return b"".join(out)


def _map(fn, jobs, label=""):
    """fn over jobs in order, on every core when there is more than one job;
    the integer partial sums make the result independent of the split. A
    `label` prints a chunk counter while it runs."""
    tick = _Progress(label, len(jobs), " chunks") if label else (lambda n=1: None)
    if len(jobs) < 2:
        out = []
        for j in jobs:
            out.append(fn(j))
            tick()
    else:
        import concurrent.futures
        with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count() or 1) as pool:
            out = []
            for part in pool.map(fn, jobs):
                out.append(part)
                tick()
    if label:
        tick.close()
    return out


def _jacobi(a):
    """(eigenvalues, eigenvectors as lists) of the symmetric matrix `a` (list of
    rows, modified in place): cyclic Jacobi rotations (Numerical Recipes'
    `jacobi`), deterministic because it uses only + - * / and sqrt."""
    n = len(a)
    vt = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for sweep in range(100):
        if not any(a[p][q] for p in range(n) for q in range(p + 1, n)):
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                apq = a[p][q]
                if not apq:
                    continue
                g = 100.0 * abs(apq)
                if sweep > 3 and abs(a[p][p]) + g == abs(a[p][p]) \
                        and abs(a[q][q]) + g == abs(a[q][q]):
                    a[p][q] = a[q][p] = 0.0
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * apq)
                t = 1.0 / (abs(theta) + math.sqrt(theta * theta + 1.0))
                if theta < 0:
                    t = -t
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                rp, rq = a[p], a[q]
                newp = [c * x - s * y for x, y in zip(rp, rq)]
                newq = [s * x + c * y for x, y in zip(rp, rq)]
                newp[p], newq[q] = rp[p] - t * apq, rq[q] + t * apq
                newp[q] = newq[p] = 0.0
                a[p], a[q] = newp, newq
                for j in range(n):
                    a[j][p], a[j][q] = newp[j], newq[j]
                vp, vq = vt[p], vt[q]
                vt[p] = [c * x - s * y for x, y in zip(vp, vq)]
                vt[q] = [s * x + c * y for x, y in zip(vp, vq)]
    return [a[i][i] for i in range(n)], vt


def _tokenizer(path, vocab):
    """(header fields, rows kept) from a tokenizer.json, as the research export."""
    with open(path, encoding="utf-8") as fh:
        tok = json.load(fh)
    model = tok["model"]
    if model["type"] == "WordPiece":
        norm = tok["normalizer"]
        tokens = [None] * len(model["vocab"])
        for t, i in model["vocab"].items():
            tokens[i] = t
        return {"tokenizer": "wordpiece", "unk_token": model["unk_token"],
                "unk_id": model["vocab"][model["unk_token"]],
                "prefix": model["continuing_subword_prefix"],
                "max_input_chars_per_word": model["max_input_chars_per_word"],
                "lowercase": norm.get("lowercase", True),
                "strip_accents": norm.get("strip_accents"), "vocab": tokens}, len(tokens)
    pieces = model["vocab"]
    keep = len(pieces)
    if vocab == "base":
        # drop the trailing run of pieces that share the minimum score
        while keep > 0 and pieces[keep - 1][1] == pieces[-1][1]:
            keep -= 1
    ops = []

    def walk(n):
        """The normalizer as ordered ops; Precompiled (the SentencePiece charsmap)
        is stood in for by NFKC in the reader."""
        kind = n["type"]
        if kind == "Sequence":
            for c in n["normalizers"]:
                walk(c)
        elif kind == "Precompiled":
            ops.append(["nfkc"])
        elif kind == "Replace" and "String" in n["pattern"]:
            ops.append(["str", n["pattern"]["String"], n["content"]])
        elif kind == "Replace" and "Regex" in n["pattern"]:
            ops.append(["re", n["pattern"]["Regex"], n["content"]])
        elif kind == "Strip":
            ops.append(["strip", n.get("strip_left", True), n.get("strip_right", True)])
        else:
            raise ValueError("normalizer %s not supported by the stdlib reader" % kind)
    walk(tok["normalizer"])
    return {"tokenizer": "unigram", "unk_id": model["unk_id"], "replacements": ops,
            "skip_pieces": ["[PAD]", "[UNK]"],
            "pieces": [list(p) for p in pieces[:keep]]}, keep


CHUNK = 8192


def convert(spec, model_file, tokenizer_file, out):
    """Write the compact model file for `spec` from its two source files."""
    meta, rows = _tokenizer(tokenizer_file, spec["vocab"])
    base, total, cols = _tensor(model_file)
    if rows > total or spec["dims"] > cols:
        raise ValueError("the tokenizer and the table do not fit together")
    spans = [(model_file, base, cols, s, min(s + CHUNK, rows))
             for s in range(0, rows, CHUNK)]
    dims = spec["dims"]
    if spec["dims_mode"] == "head":
        body = _map(_head_part, [j + (dims,) for j in spans], "quantised")
    else:
        top = max(_map(_absmax_part, spans, "scanned 1/3"), default=0.0)
        shift = 20 - math.frexp(top)[1] if top else 0
        if rows >= 1 << 23:  # 2**40 per product: the 64-bit field must hold the sum
            raise ValueError("too many rows for the fixed-point Gram matrix")
        gram = [sum(col) for col in zip(*_map(_gram_part, [j + (shift,) for j in spans],
                                              "gram 2/3"))]
        print("    solving %dx%d eigenproblem" % (cols, cols), flush=True)
        values, vt = _jacobi([[float(v) for v in _unpack(g, cols)] for g in gram])
        order = sorted(range(cols), key=lambda i: (-values[i], i))[:dims]
        axes = [_pack([round(math.ldexp(vt[k][d], 30)) for k in order]) for d in range(cols)]
        body = _map(_pca_part, [j + (axes, dims) for j in spans], "projected 3/3")
    meta.update({"repo": spec["repo"], "revision": spec["revision"],
                 "sources": {r: f[1] for r, f in sorted(spec["files"].items())},
                 "dims_mode": spec["dims_mode"], "dim": dims, "rows": rows,
                 "dtype": "int8"})
    header = json.dumps(meta, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":")).encode("utf-8")
    with open(out, "wb") as fh:
        fh.write(MAGIC + struct.pack("<Q", len(header)) + header)
        for part in body:
            fh.write(part)


def _sweep(directory):
    """Delete the `.fetch-*` work dirs in `directory`: a fetch killed by SIGKILL
    (the installer's timeout, Ctrl-C) skips its `finally` and leaves a partial
    download of ~0.5 GB. Only real directories with that prefix; a symlink is
    never followed."""
    try:
        names = os.listdir(directory)
    except OSError:
        return
    for name in names:
        path = os.path.join(directory, name)
        if name.startswith(".fetch-") and os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)


def fetch(ident, get=None):
    """Download, verify, convert and install the model for `ident`; returns its
    path. Raises on any mismatch, leaving no model file and no temp file."""
    import tempfile
    spec = MODELS[ident]
    get = get or _download
    final = model_path(ident)
    os.makedirs(os.path.dirname(final), mode=0o700, exist_ok=True)
    # ponytail: assumes one fetch at a time; a second concurrent fetch would
    # sweep the first one's work dir and fail it
    _sweep(os.path.dirname(final))
    work = tempfile.mkdtemp(prefix=".fetch-", dir=os.path.dirname(final))
    try:
        files = {}
        for role, (rel, sha) in sorted(spec["files"].items()):
            print("  fetching %s@%s %s" % (spec["repo"], spec["revision"][:12], rel),
                  flush=True)
            files[role] = os.path.join(work, role)
            got = get(URL % (spec["repo"], spec["revision"], rel), files[role])
            if got != sha:
                raise ValueError("%s: sha256 %s, pinned %s" % (rel, got, sha))
        print("  converting (%s, %d dims, int8)" % (spec["dims_mode"], spec["dims"]),
              flush=True)
        tmp = os.path.join(work, "model.bin")
        convert(spec, files["model"], files["tokenizer"], tmp)
        got = _sha256(tmp)
        if got != spec["sha256"]:
            raise ValueError("converted file sha256 %s, pinned %s" % (got, spec["sha256"]))
        os.chmod(tmp, 0o600)
        os.replace(tmp, final)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return final


def remove(ident):
    """Delete the model file for `ident` and any leftover fetch work dir; True
    when there was a model file."""
    _sweep(os.path.dirname(model_path(ident)))
    try:
        os.remove(model_path(ident))
        return True
    except OSError:
        return False


def main(argv):
    if len(argv) != 2 or argv[0] != "fetch" or argv[1] not in MODELS:
        sys.stderr.write("usage: tezgah_embed.py fetch {%s}\n" % ",".join(MODELS))
        return 2
    try:
        print("  %s -> %s" % (argv[1], fetch(argv[1])))
    except Exception as exc:  # one line for the installer's log
        sys.stderr.write("tezgah_embed: %s: %s\n" % (argv[1], exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
