#!/usr/bin/env python3
"""Seeded corpora for the `shards` command: documents spread over several shards.

Each corpus line is {"shard":s,"did":local docid,"key":hex,"terms":[...]}; the first line
is {"shards":S}. Local docids ascend within a shard and skip some numbers. Keys are short
byte strings with many ties, some empty, some holding 0x00 and 0xff bytes.
Usage: gen-shards.py OUTDIR
"""
import json
import random
import sys

CONFIGS = [
    # name, shards, documents, which shards receive documents (weights)
    ("s1", 1, 220, [1]),
    ("s2", 2, 260, [1, 1]),
    ("s3", 3, 300, [3, 2, 1]),
    ("s5", 5, 320, [1, 1, 1, 1, 1]),
    ("s5e", 5, 280, [0, 4, 1, 0, 2]),  # shards 0 and 3 stay empty
    ("s7", 7, 300, [9, 1, 1, 2, 1, 1, 1]),
]

KEYS = [b"", b"a", b"a\x00", b"a\x00b", b"b", b"ab", b"abc", b"\xff", b"\xff\x00", b"\x00", b"m", b"mm", b"z"]


def vocab_term(r):
    # Skewed: small ids are frequent. w0 is in every document.
    return "w%d" % int(r.random() ** 2 * 40)


def build(name, shards, docs, weights, seed):
    r = random.Random(seed)
    nxt = [0] * shards
    lines = [json.dumps({"shards": shards}, separators=(",", ":"))]
    for i in range(docs):
        s = r.choices(range(shards), weights)[0]
        nxt[s] += 1 + (r.random() < 0.15) * r.randint(1, 3)  # gaps in local docids
        terms = ["w0"] + [vocab_term(r) for _ in range(r.randint(2, 13))]
        if r.random() < 0.1 and i > 0:  # an exact copy of an earlier document's terms: score ties
            terms = prior[r.randrange(len(prior))]
        r.shuffle(terms)
        prior.append(terms)
        key = r.choice(KEYS) if r.random() < 0.8 else b""
        lines.append(json.dumps({"shard": s, "did": nxt[s], "key": key.hex(), "terms": terms}, separators=(",", ":")))
    return "\n".join(lines) + "\n"


prior = []
out = sys.argv[1]
for n, (name, shards, docs, weights) in enumerate(CONFIGS):
    prior.clear()
    with open("%s/shards-%s.jsonl" % (out, name), "w") as f:
        f.write(build(name, shards, docs, weights, 40 + n))

# Queries: "TERM a", "OR a b c", "AND a b", "AND_MAYBE a b", "AND_NOT a b", "PHRASE a b [c]".
r = random.Random(7)
qs = ["TERM w0", "TERM w1", "TERM w39", "TERM nosuchterm", "OR w0 nosuchterm", "AND w1 nosuchterm"]
for _ in range(8):
    qs.append("TERM w%d" % int(r.random() ** 2 * 40))
for op, lo, hi in (("OR", 2, 4), ("AND", 2, 3), ("AND_MAYBE", 2, 2), ("AND_NOT", 2, 2), ("PHRASE", 2, 3)):
    for _ in range(6):
        ts = []
        while len(ts) < r.randint(lo, hi):
            t = "w%d" % int(r.random() ** 2 * 40)
            if t not in ts:
                ts.append(t)
        qs.append(op + " " + " ".join(ts))
with open(out + "/shards-queries.txt", "w") as f:
    f.write("\n".join(qs) + "\n")
