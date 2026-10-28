#!/usr/bin/env python3
"""Generates the operator vectors' inputs: a seeded corpus (inputs/ops-corpus.jsonl) and
queries (inputs/ops-queries.txt), one s-expression per line:

    w3  w3*2          a term, with a within-query frequency
    (OP q q ...)      AND OR AND_NOT XOR AND_MAYBE FILTER SYNONYM MAX
    (ELITE_SET n q q ...)   n is the elite set size (0 is Xapian's default)
    (SCALE f q)       OP_SCALE_WEIGHT
    (SCALEN f q q)    OP_SCALE_WEIGHT through the n-ary constructor, as an operator list

Usage: gen-ops.py DIR   (writes DIR/ops-corpus.jsonl and DIR/ops-queries.txt)
"""
import json, random, sys, os

rnd = random.Random(7)
NDOCS = 600
VOCAB = [f"w{i}" for i in range(40)]


def make_corpus():
    docs = []
    for d in range(NDOCS):
        n = rnd.choice([2, 3, 4, 6, 8, 12, 20, 30, 45])
        toks = [VOCAB[int(40 * rnd.random() ** 2.5)] for _ in range(n)]
        if d % 11 == 0:  # bursty: one term repeated, so wdf varies widely
            toks += [VOCAB[rnd.randrange(40)]] * rnd.randrange(3, 12)
        if d % 97 == 5:
            toks.append("r1")
        if d % 150 == 7:
            toks.append("r2")
        if d == 311:
            toks += ["r3"] * 4
        rnd.shuffle(toks)
        docs.append(toks)
    return docs


def terms(k, lo=0, hi=40):
    out = []
    while len(out) < k:
        t = VOCAB[rnd.randrange(lo, hi)]
        if t not in out:
            out.append(t)
    return out


def op(name, *args):
    return "(" + " ".join([name, *[str(a) for a in args]]) + ")"


def make_queries():
    q = []
    rare, mid, common = (30, 40), (10, 30), (0, 10)
    bands = [rare, mid, common]
    pools = [rare, mid, common, (0, 40)]
    # SYNONYM: widths 1..6 across bands; with wqf; repeated and absent terms; nested.
    for width in (1, 2, 3, 4, 6):
        for rep in range(8):
            ts = terms(width, *rnd.choice(pools))
            q.append(op("SYNONYM", *ts))
    for rep in range(10):
        a, b = terms(2, *rnd.choice(pools))
        q.append(op("SYNONYM", a + "*2", b))
        q.append(op("SYNONYM", a, a))
    for rep in range(6):
        q.append(op("SYNONYM", *terms(2), "zz"))
        q.append(op("SYNONYM", "zz", "yy"))
    for rep in range(14):
        a, b, c, d = terms(4, *rnd.choice(pools))
        q.append(op("AND", op("SYNONYM", a, b), c))
        q.append(op("OR", op("SYNONYM", a, b), op("SYNONYM", c, d)))
        q.append(op("AND_MAYBE", c, op("SYNONYM", a, b)))
    q.append(op("SYNONYM", "r1", "r2", "r3"))
    q.append(op("SYNONYM", "r1", "w0"))
    # SYNONYM over a subquery (not a term): what Xapian does
    for rep in range(6):
        a, b, c = terms(3)
        q.append(op("SYNONYM", op("AND", a, b), c))
        q.append(op("SYNONYM", op("PHRASE", 2, a, b), c))
    # MAX
    for width in (1, 2, 3, 5):
        for rep in range(10):
            q.append(op("MAX", *terms(width, *rnd.choice(pools))))
    for rep in range(8):
        a, b, c = terms(3)
        q.append(op("MAX", op("AND", a, b), c))
        q.append(op("MAX", a, "zz"))
        q.append(op("OR", op("MAX", a, b), c))
        q.append(op("AND", op("MAX", a, b), c))
        q.append(op("MAX", a + "*3", b))
    # XOR
    for width in (1, 2, 3, 4, 5):
        for rep in range(10):
            q.append(op("XOR", *terms(width, *rnd.choice(pools))))
    for rep in range(10):
        a, b, c, d = terms(4)
        q.append(op("XOR", op("AND", a, b), c))
        q.append(op("XOR", a, "zz"))
        q.append(op("XOR", "zz", "yy"))
        q.append(op("AND", op("XOR", a, b), c))
        q.append(op("OR", op("XOR", a, b), op("XOR", c, d)))
        q.append(op("XOR", op("XOR", a, b), c))
        q.append(op("XOR", a, a))
        q.append(op("XOR", a + "*2", b))
    # SCALE
    for f in (0, 0.25, 0.5, 1, 2, 3.7, 100, 1e-9):
        for rep in range(5):
            a, b, c = terms(3, *rnd.choice(pools))
            q.append(op("SCALE", f, a))
            q.append(op("SCALE", f, op("OR", a, b)))
            q.append(op("SCALE", f, op("AND", a, b)))
            q.append(op("OR", op("SCALE", f, a), c))
            q.append(op("AND", op("SCALE", f, a), c))
    for f in (-1, -0.5):
        q.append(op("SCALE", f, "w1"))
    for f in (0.5, 2):
        q.append(op("SCALEN", f, "w1", "w2"))
        q.append(op("SCALEN", f, "w1"))
    q.append(op("SCALE", 2, "zz"))
    q.append(op("SCALE", 2, op("SCALE", 3, "w4")))
    # FILTER against AND with a zero scale
    for rep in range(12):
        a, b = terms(2, *rnd.choice(pools))
        q.append(op("FILTER", a, b))
        q.append(op("AND", a, op("SCALE", 0, b)))
        q.append(op("FILTER", op("OR", a, b), op("OR", *terms(2))))
    # ELITE_SET
    for rep in range(40):
        n = rnd.choice([3, 4, 5, 6, 8, 10, 12])
        size = rnd.choice([0, 1, 2, 3, 4, 5, n, n + 2])
        pool = rnd.choice(pools)
        ts = terms(min(n, pool[1] - pool[0]), *pool)
        q.append(op("ELITE_SET", size, *ts))
    for rep in range(16):
        ts = terms(6)
        q.append(op("ELITE_SET", 2, ts[0] + "*3", *ts[1:]))
        q.append(op("ELITE_SET", 3, *[t + ("*2" if i % 2 else "") for i, t in enumerate(ts)]))
    for rep in range(10):
        ts = terms(6)
        q.append(op("ELITE_SET", 2, op("AND", ts[0], ts[1]), ts[2], ts[3], op("AND", ts[4], ts[5])))
        q.append(op("ELITE_SET", 3, op("OR", ts[0], ts[1]), ts[2], ts[3], ts[4]))
        q.append(op("ELITE_SET", 2, ts[0], ts[1], "zz", "yy"))
        q.append(op("AND", op("ELITE_SET", 2, *ts), ts[0]))
    q.append(op("ELITE_SET", 0, *VOCAB[:20]))
    q.append(op("ELITE_SET", 0, *VOCAB[:40]))
    q.append(op("ELITE_SET", 10, *VOCAB))
    q.append(op("ELITE_SET", 1, "w3"))
    q.append(op("ELITE_SET", 2, "r1", "r2", "r3", "w39"))
    # Controls: operators prospect has already
    for rep in range(6):
        a, b, c = terms(3)
        q.append(op("OR", a, b, c))
        q.append(op("AND", a, b, c))
    return q


def main(out):
    docs = make_corpus()
    with open(os.path.join(out, "ops-corpus.jsonl"), "w") as f:
        for i, t in enumerate(docs):
            f.write(json.dumps({"doc": i + 1, "terms": t}, separators=(",", ":")) + "\n")
    with open(os.path.join(out, "ops-queries.txt"), "w") as f:
        for line in make_queries():
            f.write(line + "\n")


main(sys.argv[1])
