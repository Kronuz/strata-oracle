#!/usr/bin/env python3 -I
"""Writes the specs that `oracle parse-v2` records for parse-v3: targeted variations of the query shapes
where the queryparser's T2 run against parse-v2 still fails, plus the four open shapes of CR2.

Usage: gen-parse-v3.py > inputs/parse-v3.tsv

Each group is one shape. A shape is a few templates (`{0}`, `{1}`... are operands) crossed with operand
patterns and parser configurations, so each row differs from its neighbours by one factor:

  operand pattern  S single-letter stop words (a b c d), T ordinary stop words (the an of is),
                   N non-stop words (foo bar baz qux); one letter per operand, e.g. "SN"
  configuration    see CFG: default operator, BOOLEAN, partial and wildcard flags, stopper, stemmer

The base configuration is Xapiand's (get_term_query / parse_text): PHRASE, LOVEHATE and FUZZY, the English
stopper, STEM_SOME with the English stemmer, prefix "S", partial 50 most_frequent. Rows are never
rewritten (no trailing `*` handling): `query` is the exact string handed to the parser.
"""
import json
import sys

WORDS = {"S": "a b c d".split(), "T": "the an of is".split(), "N": "foo bar baz qux".split()}
FLAG_ORDER = ["boolean", "phrase", "lovehate", "boolean_any_case", "wildcard", "pure_not", "partial", "cjk_ngram",
              "word_breaks", "wildcard_multi", "wildcard_single", "fuzzy"]
PLAIN_OPS = ("near", "phrase", "elite_set", "synonym", "max")
WILD_ALL = ("wildcard", "wildcard_multi", "wildcard_single")

# name -> overrides of the base configuration.
CFG = {
    "and": dict(op="and"),
    "or": dict(op="or"),
    "unset": dict(op="unset"),
    "xor": dict(op="xor"),
    "and-nobool": dict(op="and", boolean=False),
    "unset-bool": dict(op="unset", boolean=True),
    "and-partial": dict(op="and", extra=("partial",)),
    "or-partial": dict(op="or", extra=("partial",)),
    "unset-partial": dict(op="unset", extra=("partial",)),
    "and-wild": dict(op="and", extra=("wildcard",)),
    "and-wildall": dict(op="and", extra=WILD_ALL),
    "and-both": dict(op="and", extra=("wildcard", "partial")),
    "unset-wild": dict(op="unset", extra=("wildcard",)),
    "and-nostop": dict(op="and", stop=""),
    "unset-nostop": dict(op="unset", stop=""),
    "and-nostem": dict(op="and", stem="unset"),
    "and-bare": dict(op="and", stop="", stem="unset"),
    "and-allz": dict(op="and", stem="all_z"),
    "and-stopall": dict(op="and", stop_strategy="all"),
    "and-stopnone": dict(op="and", stop_strategy="none"),
    "unset-stopall": dict(op="unset", stop_strategy="all"),
    "unset-stopnone": dict(op="unset", stop_strategy="none"),
    "and-nolovehate": dict(op="and", flags=("boolean", "phrase", "fuzzy")),
    "and-onlybool": dict(op="and", flags=("boolean",)),
    "unset-nolovehate": dict(op="unset", flags=("phrase", "fuzzy")),
    "unset-noflags": dict(op="unset", flags=()),
    "and-purenot": dict(op="and", extra=("pure_not",)),
    "unset-purenot": dict(op="unset", extra=("pure_not",)),
    "and-anycase": dict(op="and", extra=("boolean_any_case",)),
    "near": dict(op="near"),
    "phrase": dict(op="phrase"),
    "and-title": dict(op="and", prefix="title.S"),
    "unset-title": dict(op="unset", prefix="title.S"),
    "and-cjk": dict(op="and", extra=("cjk_ngram",)),
    "unset-cjk": dict(op="unset", extra=("cjk_ngram",)),
}

rows = []
seen = set()
counts = {}


def pats(k, full=True):
    """Operand patterns for k operands: all stop, all non-stop, and one stop word first (and last when k < 4)."""
    out = ["S" * k, "N" * k]
    if full and k > 1:
        out += ["S" + "N" * (k - 1), "N" * (k - 1) + "S"] if k > 2 else ["SN", "NS"]
    return out


def emit(group, query, cfg):
    c = dict(op="unset", boolean=None, extra=(), stop="en", stem="some", prefix="S", stop_strategy="default",
             flags=None)
    c.update(CFG[cfg])
    if c["flags"] is not None:
        flags = set(c["flags"])
    else:
        flags = {"phrase", "lovehate", "fuzzy"}
        if c["op"] in ("and", "or") if c["boolean"] is None else c["boolean"]:
            flags.add("boolean")
    flags |= set(c["extra"])
    plain = c["op"] in PLAIN_OPS
    stopper = c["stop"] if c["stop"] and not plain else "none"
    use_stem = c["stem"] != "unset" and not plain
    fl = "|".join(f for f in FLAG_ORDER if f in flags) or "-"
    key = (group, query, fl, c["op"], stopper, c["stop_strategy"], use_stem and c["stem"], c["prefix"])
    if key in seen:
        return
    seen.add(key)
    counts[group] = counts.get(group, 0) + 1
    rows.append("\t".join([group, json.dumps(query, ensure_ascii=False), fl, c["op"], stopper, c["stop_strategy"],
                           "english" if use_stem else "none", c["stem"] if use_stem else "unset",
                           json.dumps(c["prefix"]), "50", "most_frequent", "0", "error", "0", "error", "0"]))


def block(group, templates, opsets, cfgs):
    """Every template x operand pattern (of the template's operand count) x configuration."""
    for t in templates:
        k = max([i for i in range(8) if "{%d}" % i in t], default=-1) + 1
        ps = [p for p in opsets if len(p) == k] if k else [""]
        for p in ps:
            q = t.format(*[WORDS[ch][i] for i, ch in enumerate(p)])
            for cfg in cfgs:
                emit(group, q, cfg)


def literal(group, queries, cfgs):
    for q in queries:
        for cfg in cfgs:
            emit(group, q, cfg)


# Configurations: BOOLEAN with default operator AND, OR and unset; BOOLEAN absent; no stopper; the partial and
# wildcard flags (a `*` in the query adds all three wildcard flags).
P7 = ["and", "or", "unset", "and-nobool", "and-nostop", "and-partial", "and-wild"]
P7S = ["and", "or", "unset", "and-nobool", "and-nostop", "and-partial", "and-wildall"]
MINUS = ["and", "or", "unset", "and-nobool", "and-nostop", "and-nolovehate", "and-purenot"]
STOPS = ["and", "unset", "unset-partial", "unset-nostop", "unset-stopall", "unset-stopnone", "unset-purenot", "unset-noflags"]
TILDE = ["and", "or", "unset", "and-nobool", "and-nostop", "and-wild", "and-title", "unset-title"]


def operands(t):
    return max([i for i in range(8) if "{%d}" % i in t], default=-1) + 1


def family(slug, primary, minors=(), cfgs=None, minor_cfgs=("and", "unset"), extra_pats=()):
    """One group: the primary template over every operand pattern and configuration, then each neighbouring
    template (a different position, operator or sign) over the all-stop and all-non-stop patterns."""
    k = operands(primary)
    ps = pats(k) if k else [""]
    if k == 1:
        ps = ps + ["T"]
    ps = ps + [p for p in extra_pats if len(p) == k]
    for p in ps:
        q = primary.format(*[WORDS[ch][i] for i, ch in enumerate(p)])
        for cfg in cfgs or (P7S if "*" in primary else P7):
            emit(slug, q, cfg)
    for t in minors:
        k = operands(t)
        for p in (["S" * k, "N" * k] if k else [""]):
            q = t.format(*[WORDS[ch][i] for i, ch in enumerate(p)])
            for cfg in minor_cfgs + (("and-wild",) if "*" in t else ()):
                emit(slug, q, cfg)


def main():
    # --- stop words beside stray or unclosed brackets ---------------------------------------
    family("close-after", "{0}) {1}", ["{0} ){1}", "){0} {1}", "{0} {1})"])
    family("close-group", "{0} ({1}) {2})", ["{0} OR {1}) {2}", "{0} NEAR {1})", "{0}){1}"])
    family("close-lead-star", "){0}*", [")", "){0}", ") {0}*"])
    family("open-glued", "{0}( {1}", ["{0} ({1}", "{0}({1}", "({0} {1}"])
    family("open-nested", "({0} OR ({1}", ["{0} OR ({1}", "(({0} {1}", "({0}"])
    family("open-quote", "({0} \"{1} {2}*", ["({0} \"{1} {2}", "{0} \"{1} {2}"])
    family("near-paren", "({0}) NEAR ({1})", ["({0}) NEAR ({1}", "({0}) ADJ ({1})", "({0}) NEAR/3 ({1})"])
    family("near-paren-mixed", "({0}) NEAR {1}", ["{0} NEAR ({1})", "({0} {1}) NEAR {2}", "({0}) AND ({1})"])
    family("glued-call", "{0}({1})", ["{0}-({1})", "{0}+({1})", "({0}){1}"])
    family("glued-call-tail", "{0}({1}) {2}", ["{0}.({1})", "{0}:({1})", "{0}({1}){2}"])

    # --- NEAR and ADJ beside quotes, +b, expanding words, bare, boolean words --------------------
    family("near-quote-left", "\"{0} {1}\" NEAR {2}", ["\"{0} {1}\" ADJ {2}", "\"{0} {1}\" NEAR/3 {2}", "\"{0} {1}\" AND {2}"])
    family("near-quote-right", "{0} NEAR \"{1} {2}\"", ["{0} ADJ \"{1} {2}\"", "{0} NEAR/3 \"{1} {2}\"", "{0} AND \"{1} {2}\""])
    family("near-quote-both", "\"{0} {1}\" NEAR \"{2} {3}\"", ["\"{0}\" NEAR {1}", "{0} NEAR \"{1}\"", "\"{0} {1}\" {2}"])
    family("near-plus", "{0} NEAR +{1}", ["{0} ADJ +{1}", "{0} NEAR/3 +{1}", "{0} NEAR + {1}"])
    family("near-plus-left", "+{0} NEAR {1}", ["-{0} NEAR {1}", "{0} NEAR -{1}", "+{0} NEAR +{1}"])
    family("plus-ops", "{0} AND +{1}", ["{0} OR +{1}", "{0} +{1}", "{0} NEAR +{1} {2}"])
    family("near-plus-star", "{0} NEAR +{1}*", ["+{0} NEAR {1}*", "{0} NEAR {1} +{2}", "{0} NEAR +{1} {2}"])
    family("near-trail", "{0} NEAR", ["{0} ADJ", "{0} AND", "{0} NEAR/3"])
    family("near-lead-star", "NEAR {0}*", ["NEAR/3 {0}*", "NEAR {0}", "NEAR/3 {0}"])
    family("near-only", "NEAR", ["NEAR/3", "ADJ", "AND", "NEAR NEAR"])
    family("near-twice", "{0} NEAR/3 NEAR/3 {1}*", ["{0} NEAR/3 NEAR/3 {1}", "{0} NEAR NEAR {1}", "{0} NEAR/3 NEAR {1}"])
    family("near-hyphen-star", "{0}-{1} NEAR {2}*", ["{0}-{1} NEAR {2}", "{0}-{1} NEAR {2}-{3}*", "{0}* NEAR {1}*"])
    family("near-quote-star", "\"{0} {1}\" NEAR {2}*", ["({0} {1}) NEAR {2}*", "{0} NEAR {1}*", "+{0} NEAR {1}*"])
    family("near-dotted-star", "{0} NEAR {1}.{2}.{3}*", ["{0} NEAR {1}.{2}.{3}", "{0} NEAR/3 ({1} {2}) NEAR {3}*"])
    family("near-win-and", "{0} NEAR/3 AND {1}", ["{0} NEAR AND {1}", "{0} ADJ/3 AND {1}", "{0} NEAR/3 and {1}"])
    family("near-win-bool", "{0} NEAR/3 OR {1}", ["{0} NEAR/3 NOT {1}", "{0} NEAR/3 XOR {1}", "{0} AND NEAR/3 {1}"])
    family("near-win-and-trail", "{0} NEAR/3 AND", ["{0} NEAR/3 AND {1} {2}", "{0} NEAR/3 {1}", "{0} NEAR/3 -{1}"])

    # --- minus and plus ---------------------------------------------------------------------------
    family("minus-quote", "-\"{0} {1}\" {2}", ["{0} -\"{1} {2}\"", "-\"{0} {1}\"", "+\"{0} {1}\" {2}"], MINUS)
    family("minus-group", "-({0} {1}) {2}", ["-({0}) {1}", "{0} -({1} {2})", "-({0} {1})"], MINUS)
    family("minus-lead-or", "-{0} OR {1}", ["-{0} XOR {1}", "-{0} NOT {1}", "{0} NOT -{1}"], MINUS)
    family("minus-last", "{0} {1} -{2}", ["{0} -{1} {2}", "{0} -{1}", "{0} {1} {2}"], MINUS)
    family("minus-first", "-{0} {1} {2}", ["-{0} {1}", "-{0} -{1} {2}", "{0} -{1} -{2}"], MINUS)
    family("minus-last-of-4", "{0} {1} {2} -{3}", ["-{0} {1} {2} {3}", "{0} {1} -{2} {3}", "{0} {1} -{2} -{3}"], MINUS)
    family("minus-and", "{0} AND -{1}", ["-{0} AND {1}", "{0} AND +{1}", "{0} AND NOT {1}"], MINUS)
    family("stop-minus", "-{0}", ["+{0}", "--{0}", "-{0} -{1} -{2}"], STOPS, minor_cfgs=("unset", "unset-partial"), extra_pats=("TT",))
    family("stop-minus-two", "-{0} -{1}", ["+{0} -{1}", "-{0} +{1}", "-{0} {1}"], STOPS, minor_cfgs=("unset",), extra_pats=())

    # --- CR2's four open shapes: the shape itself, then one factor changed at a time ----------------
    cr2 = MINUS
    family("cr2-or-minus", "{0} OR -{1}", ["{0} OR --{1}", "{0} OR +{1}", "{0} OR NOT {1}", "{0} OR{1}"], cr2)
    family("cr2-or-minus-forms", "{0} OR -{1} -{2}", ["{0} OR -{1} {2}", "-{0} OR -{1}", "{0} OR -\"{1} {2}\"", "{0} OR -({1})", "{0} OR - {1}", "{0} OR -", "{0} OR ---{1}"],
           ["and", "or", "unset", "and-nobool"])
    family("cr2-xor-minus", "{0} XOR -{1}", ["{0} XOR --{1}", "{0} XOR +{1}", "{0} XOR NOT {1}", "{0} XOR{1}"], cr2)
    family("cr2-xor-minus-forms", "{0} XOR -{1} -{2}", ["{0} XOR -{1} {2}", "-{0} XOR -{1}", "{0} XOR -\"{1} {2}\"", "{0} XOR -({1})", "{0} XOR - {1}", "{0} XOR -", "{0} XOR ---{1}"],
           ["and", "or", "unset", "and-nobool"])
    family("cr2-and-not-minus", "{0} AND NOT -{1}", ["{0} AND NOT --{1}", "{0} AND NOT +{1}", "{0} AND NOT {1}", "{0} NOT -{1}"], cr2)
    family("cr2-and-not-minus-forms", "{0} AND NOT -{1} -{2}", ["{0} AND NOT -{1} {2}", "{0} AND NOT NOT {1}", "{0} AND NOT -\"{1} {2}\"", "{0} AND NOT -({1})", "{0} AND NOT - {1}", "{0} AND NOT -", "NOT -{0}", "{0} OR NOT -{1}"],
           ["and", "or", "unset", "and-nobool"])
    family("cr2-and-doubleminus", "{0} AND --{1}", ["{0} AND ---{1}", "{0} AND -+{1}", "{0} AND +-{1}", "{0} AND ++{1}"], cr2)
    family("cr2-and-doubleminus-forms", "--{0} {1}", ["--{0}", "{0} --{1}", "{0} --{1} {2}", "{0} AND --{1} {2}", "{0} AND --\"{1} {2}\"", "{0} AND --({1})", "{0} AND - -{1}"],
           ["and", "or", "unset", "and-nobool"])

    # --- the remaining open rows ------------------------------------------------------------------
    family("tilde-minus-digit", "{0}~-1", ["{0}~-", "{0}~1", "{0}~0", "{0}~-1 {1}"], TILDE)
    family("tilde-star-or", "{0}*~ OR~ {1}*~", ["{0}~ OR~ {1}~", "{0}~ OR {1}~", "{0} OR~ {1}"], TILDE[:5] + ["and-wildall", "and-title", "unset-title"])
    family("tilde-digit-star", "{0}~2 {1}~1*", ["{0}~ {1}", "{0}~~", "{0}~a"], TILDE[:5] + ["and-wildall", "and-title", "unset-title"])
    family("backslash-open", "{0}\\({1}", ["{0}\\){1}", "{0}\\-{1}", "\\({0}", "{0}\\ {1}", "{0}\\\"{1}", "{0}\\\\{1}"], ["and", "or", "unset", "and-nobool", "and-nostop"])
    cj = ["中文AND分词", "中文 AND 分词", "中文AND", "AND分词", "中文OR分词", "中文and分词", "a AND 分词", "中文AND b", "中文分词", "中文 分词"]
    literal("cjk-op", cj, ["and-cjk", "and", "unset-cjk"])
    literal("cjk-phrase", ["\"中文分词\"", "\"中文\"", "\"分词\"", "\"中文 分词\"", "\"a 中文\"", "\"中文 a\"", "\"中文分词", "中文\"分词\"",
                           "-\"中文分词\"", "+\"中文分词\"", "\"中文分词\" foo", "\"中文分词\" NEAR foo"],
            ["unset-cjk", "and-cjk", "unset", "and-nostop"])

    sys.stdout.write("\n".join(rows) + "\n")
    for k, v in counts.items():
        print(f"{k}\t{v}", file=sys.stderr)


if __name__ == "__main__":
    main()
