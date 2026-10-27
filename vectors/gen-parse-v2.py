#!/usr/bin/env python3 -I
"""Writes the specs that `oracle parse-v2` records: Xapiand's QueryParser configurations.

Usage: gen-parse-v2.py > inputs/parse-v2.tsv

Each row is one parser configuration plus one query string. The configurations are those
Xapiand can produce for a `text` field (src/query_dsl.cc get_term_query, src/engine/xapian/
query.cc parse_text): see `xapiand()`. Groups name what a set of rows pins down; the README
maps them to the queryparser design's open items.
"""
import json
import sys

# --- Xapiand's configuration -------------------------------------------------------------

PLAIN_OPS = ("near", "phrase", "elite_set", "synonym", "max")  # no BOOLEAN, stopper or stemmer
PREFIX = "S"  # a field prefix plus the text type character


def is_word_byte(b):
    return b >= 128 or 48 <= b <= 57 or 65 <= b <= 90 or 97 <= b <= 122


def xapiand(text, op="unset", kind="plain", stem="some", lang="english", stop="en", prefix=PREFIX,
            cjk=False, extra=(), partial_max=50, partial_limit="most_frequent", fuzzy_max=0,
            fuzzy_limit="error", wildcard_max=0, wildcard_limit="error", expand=0, stop_strategy="default"):
    """The (query string, settings) Xapiand hands the parser for a user's text value.

    kind is the DSL node that carried the text: plain, wildcard (`_wildcard`), partial
    (`_partial`) or fuzzy (`_fuzzy`)."""
    flags = set(extra)
    if kind == "wildcard":
        flags.add("wildcard")
    elif kind == "partial":
        flags.add("partial")
    elif kind == "fuzzy":
        flags.add("fuzzy")
    raw = text.encode("utf-8")
    if kind == "plain":
        if raw.endswith(b"**"):
            raw = raw[:-2]
            flags.add("partial")
        elif raw.endswith(b"*"):
            if len(raw) >= 2:
                if is_word_byte(raw[-2]):
                    flags.add("wildcard")
                else:
                    raw = raw[:-1]
            else:
                flags.add("wildcard")
    if "wildcard" in flags:
        pos = min([i for i, b in enumerate(raw) if b in b"?*"], default=-1)
        if pos < 0:
            if len(raw) >= 1:
                if is_word_byte(raw[-1]):
                    raw = raw + b"*"
            else:
                raw = b"*"
        elif pos != len(raw) - 1:
            flags |= {"wildcard_single", "wildcard_multi"}
    if "fuzzy" in flags:
        words = raw.split(b" ")
        raw = b" ".join(w if b"~" in raw else w + b"~" for w in words)
    flags |= {"phrase", "lovehate", "fuzzy"}
    if op in ("and", "or"):
        flags.add("boolean")
    if cjk:
        flags.add("cjk_ngram")
    use_text = op not in PLAIN_OPS
    return dict(
        query=raw.decode("utf-8"), flags=flags, op=op,
        stopper=stop if use_text and stop else "none",
        stop_strategy=stop_strategy,
        stem_lang=lang if use_text and stem != "unset" else "none",
        stem=stem if use_text and stem != "unset" else "unset",
        prefix=prefix, partial_max=partial_max, partial_limit=partial_limit, fuzzy_max=fuzzy_max,
        fuzzy_limit=fuzzy_limit, wildcard_max=wildcard_max, wildcard_limit=wildcard_limit, expand=expand)


FLAG_ORDER = ["boolean", "phrase", "lovehate", "boolean_any_case", "wildcard", "pure_not", "partial", "cjk_ngram",
              "word_breaks", "wildcard_multi", "wildcard_single", "fuzzy"]

rows = []
seen = set()


def emit(group, **kw):
    s = xapiand(**kw)
    fl = "|".join(f for f in FLAG_ORDER if f in s["flags"]) or "-"
    key = (group, s["query"], fl, s["op"], s["stopper"], s["stop_strategy"], s["stem_lang"], s["stem"], s["prefix"],
           s["partial_max"], s["partial_limit"], s["fuzzy_max"], s["fuzzy_limit"], s["wildcard_max"], s["wildcard_limit"], s["expand"])
    if key in seen:
        return
    seen.add(key)
    rows.append("\t".join([group, json.dumps(s["query"]), fl, s["op"], s["stopper"], s["stop_strategy"], s["stem_lang"], s["stem"],
                           json.dumps(s["prefix"]), str(s["partial_max"]), s["partial_limit"], str(s["fuzzy_max"]),
                           s["fuzzy_limit"], str(s["wildcard_max"]), s["wildcard_limit"], str(s["expand"])]))


def each(group, queries, ops=("unset",), **kw):
    for op in ops:
        for q in queries:
            emit(group, text=q, op=op, **kw)


# --- queries -------------------------------------------------------------------------------

BASE = [l.rstrip("\n") for l in open("inputs/queries.txt", encoding="utf-8") if l.strip()]

# Item 1: juxtaposition precedence and chain flattening.
PRECEDENCE = [
    "a b", "a b c", "a OR b c", "a b OR c", "a AND b c", "a b AND c", "a OR b AND c", "a AND b OR c",
    "a XOR b c", "a b XOR c d", "a AND b AND c", "a OR b OR c", "a XOR b XOR c", "a AND b OR c AND d",
    "a OR b AND c OR d", "a XOR b AND c", "a AND b XOR c", "a OR b XOR c", "a XOR b OR c", "(a OR b) (c OR d)",
    "(a OR b) OR c", "a OR (b OR c)", "(a AND b) AND c", "a AND (b AND c)", "(a XOR b) XOR c", "a NOT b NOT c",
    "a NOT b c", "a b NOT c", "a AND b NOT c", "a OR b NOT c", "a NOT b OR c", "a NOT b AND c", "a AND b AND c AND d",
    "a OR b OR c OR d", "a b c d e", "(a b) (c d)", "((a b) c) d", "a (b c)", "a (b OR c) d", "a OR b c OR d",
    "a NEAR b c", "a b NEAR c", "a NEAR b AND c", "a AND b NEAR c", "a NEAR b OR c d", "a ADJ b c", "a b ADJ c",
    "\"a b\" c", "a \"b c\" d", "\"a b\" OR \"c d\"", "\"a b\" \"c d\"", "a OR b OR c d", "a AND b AND c d",
    "title:a b", "a title:b c", "(a b) OR (c d)", "(a OR b) AND (c OR d)", "(a OR b) NOT (c OR d)",
    "a XOR b XOR c XOR d", "a OR b AND c XOR d", "a b XOR c OR d",
]

# Item 2: + and -.
PLUSMINUS = [
    "+a b", "+a -b c", "a +b", "a -b", "+a -b", "-a +b", "-a", "-a b", "a -b -c", "+a +b c", "+a b c -d", "+(a b) c",
    "-(a b)", "+\"a b\" c", "-\"a b\" c", "+a-b", "+-a", "a - b", "a + b", "++a", "--a", "+", "-", "a +", "a -", "+a +",
    "-a-b", "+title:a b", "+a OR b", "a OR +b", "+a AND b", "a AND -b", "a NOT -b", "-a OR b", "+a NOT b", "(+a b)",
    "(+a -b) c", "+(a OR b) -(c d)", "+a +b", "-a -b", "-a -b c", "a -b +c", "+a b -c d", "+a b c", "a b -c",
    "-a b c", "+a -b -c d", "+a +b -c -d e", "a +b c -d e", "+a-", "+ a", "- a", "a+b", "a-b", "a -b-c", "a +b-c",
    "+(a)", "+()", "-()", "+a (b)", "+\"a\"", "+\"\"", "+a +\"b c\" -d",
]

# Item 3: NEAR/ADJ windows.
NEARADJ = ["a NEAR b", "a ADJ b", "a NEAR/3 b", "a ADJ/3 b", "a NEAR/1 b", "a ADJ/1 b", "a NEAR/2 b", "a ADJ/2 b",
           "a NEAR/0 b", "a ADJ/0 b", "a NEAR/10 b", "a NEAR/11 b", "a NEAR/100 b", "a NEAR/-1 b", "a NEAR/x b", "a NEAR/ b",
           "a NEAR/99999999999 b", "a NEAR/4294967296 b", "a NEAR/4294967295 b",
           "a NEAR b NEAR c", "a NEAR b NEAR c NEAR d", "a NEAR b NEAR c NEAR d NEAR e", "a ADJ b ADJ c", "a ADJ b ADJ c ADJ d",
           "a NEAR/3 b NEAR/3 c", "a NEAR/3 b NEAR/5 c", "a NEAR b NEAR/3 c", "a NEAR/3 b NEAR c", "a ADJ/3 b ADJ/3 c",
           "a ADJ/3 b ADJ/5 c", "a NEAR b ADJ c", "a ADJ b NEAR c", "a NEAR/3 b ADJ/3 c", "a NEAR/5 b NEAR/5 c NEAR/5 d",
           "a-b NEAR c", "a NEAR b-c", "a-b NEAR c-d", "a-b ADJ c", "\"a b\" NEAR c", "a NEAR \"b c\"", "(a b) NEAR c",
           "a NEAR (b c)", "(a) NEAR (b)", "a NEAR +b", "+a NEAR b", "-a NEAR b", "a NEAR -b", "a NEAR b c", "a b NEAR c d",
           "a NEAR NEAR b", "NEAR a", "a NEAR", "NEAR", "a near b", "a Near b", "a NEAR/3", "NEAR/3 a", "a NEAR/3 NEAR b",
           "Barack NEAR Obama", "barack NEAR obama", "running NEAR runners", "the NEAR cat", "cat NEAR the", "the NEAR the",
           "the NEAR cat NEAR mat", "cat NEAR the NEAR mat", "a NEAR b AND c", "a NEAR b OR c", "a NEAR b NOT c", "a NOT b NEAR c",
           "a AND b NEAR c NEAR d", "a OR b NEAR/3 c ADJ d", "title:a NEAR b", "a NEAR title:b", "a NEAR b*", "a* NEAR b",
           "a NEAR b~", "a~ NEAR b", "a NEAR 1990s-era", "a NEAR b.c.d", "x NEAR y NEAR z NEAR w NEAR v NEAR u",
           "a NEAR b XOR c", "a XOR b NEAR c", "a NEAR/3 (b c) NEAR d", "NEAR/3", "a NEAR/03 b", "a NEAR/+3 b"]
NEARADJ_ALT = ["a NEAR b", "a ADJ b", "a NEAR/3 b", "a NEAR b NEAR c", "a ADJ b ADJ c", "a NEAR b c", "barack NEAR obama",
               "the NEAR cat", "a NEAR", "NEAR a"]

# Item 4: phrase generators.
GEN_CHARS = ["-", ":", "/", ".", "@", "\\", "_", ",", ";", "'", "&", "+", "#", "$", "%", "!", "=", "~", "^", "*", "?",
             "|", "<", ">", "[", "]", "{", "}", "`", "\u2010", "\u2013", "\u2014", "\u2019", "\u00b7", "\u00d7", "\u2026",
             "\u00a0", "\u3000", "--", "::", "//", "..", "-.", ".-", "-_"]

# Items 5 and the brackets: unclosed ( and stray ).
PARENS = [
    "(a", "(a b", "((a", "(a OR b", "a)", "a b)", ")a", "a) b", "(a))", "(", ")", "()", "(())", "( )", "a ()", "() a",
    "(a b))", ")(", "a (b", "a (b) c)", "(a OR (b", "a OR (", "( OR a)", "(a OR )", "a OR )", "(a AND", "NOT (a", "+(a",
    "-(a", "(a \"b c", "\"(a b)\"", "a(b)", "(a)b", "(a)(b)", "a-(b)", "title:(a b)", "(a) OR (b", "a OR b)", "a OR b) c",
    "(a OR b", "((a OR b) AND c", "(a OR b)) AND c", "(((a)))", "((a) (b))", "(a (b (c (d))))", "(a b) (", ") (a b)",
    "(a OR)", "(OR a)", "(NOT a)", "(a NOT)", "(NEAR a)", "(a NEAR)", "(a NEAR b", "a NEAR b)", "(a) NEAR (b", "()()", "(()", "())",
    "+(", "-(", "+)", "-)", "(+", "(-", "(\"", "(\")", "\")", "a )b", "a( b", "a (b)c", "(a)\u00e9",
    "(" * 10 + "a" + ")" * 10, "(" * 100 + "a" + ")" * 100, "(" * 1000 + "a" + ")" * 1000, "(" * 100 + "a", "(" * 1000 + "a",
    "a" + ")" * 100, ")" * 100 + "a", "(" * 50 + "a OR b" + ")" * 50, "(a " * 50 + ")" * 50, "((a OR b) AND c) OR d",
    "(a OR b) AND (c OR d) AND (e OR f)",
]

# Missing operands, per operator (the errors).
OPERANDS = [
    "AND", "OR", "NOT", "XOR", "NEAR", "ADJ", "a AND", "a OR", "a NOT", "a XOR", "a NEAR", "a ADJ", "AND a", "OR a", "NOT a",
    "XOR a", "NEAR a", "ADJ a", "a AND AND b", "a OR OR b", "a NOT NOT b", "a XOR XOR b", "a AND OR b", "a OR AND b", "a AND NOT b",
    "a OR NOT b", "a NOT AND b", "a XOR NOT b", "a AND NOT NOT b", "a AND NOT", "AND NOT", "NOT NOT", "NOT NOT a", "a NOT NOT",
    "NOT a NOT b", "NOT a AND b", "a AND NOT b AND c", "AND OR", "OR AND", "AND AND", "OR OR", "NOT AND", "(AND)", "(a AND)", "(AND a)",
    "a AND (", "a AND )", "a AND ()", "a AND () b", "a OR () b", "() AND a", "() OR a", "a NEAR ()", "a NOT ()", "NOT ()", "AND/3",
    "a AND/3 b", "a OR/3 b", "a NOT/3 b", "a XOR/3 b", "a and b", "a or b", "a not b", "a xor b", "a near b", "a adj b", "And", "Or",
    "a And b", "a aNd b", "a NEAR/3 NEAR/3 b", "a NEAR/3 AND b", "a AND NEAR b", "a AND\u00a0b", "a  AND  b", "a\tAND\tb",
    "a AND\nb", "a-AND-b", "a.AND.b", "AND-b", "a-AND", "ANDa", "aAND", "a ANDb", "a ANDROID", "NOTa", "a NOTb", "ORb", "a ORb",
    "NOT.", ".NOT", "a AND: b", "AND:", "OR:", "NOT:", "a AND\"b c\"", "a AND \"b c\"", "\"a b\" AND", "AND \"a b\"", "\"a AND b\"",
]

# Stemming, capital letters and wildcards.
STEMMING = [
    "running", "Running", "RUNNING", "runNing", "running runners", "Running runners", "running Runners", "running*", "Running*",
    "runn*", "runn?ng", "running~", "running~2", "+running", "-running", "running running", "\"running runners\"",
    "running-runner", "title:running", "running NEAR runner", "(running)", "running AND runners", "running OR runners",
    "Running AND runners", "running:", "the running", "Barack Obama's", "Barack Obamas", "obama's", "OBAMA'S", "Obama", "obama",
    "Obama running", "obama Running", "running Obama", "1990s", "1990s-era", "running's", "runner's runners'", "runs ran run",
    "Runs", "ran", "RUNS ran", "\u00c9ric running", "\u00e9ric running", "caf\u00e9s caf\u00e9", "Caf\u00e9", "ob?ma", "obam*", "Obam*",
    "obam?", "obam**", "obamas*", "a running", "running a", "running. runners", "Running. runners", "running, Runners",
    "dogs. Cats", "i am running", "I am running", "Is running", "running IS", "iPhone running", "McDonald's", "Mc Donald's",
    "e-mail", "E-mail", "e-Mail", "Hello World", "Hello world", "hello World", "HELLO world", "Hello-world", "hello-World", "foo.Bar",
    "Foo.bar", "foo:Bar", "Foo:bar", "foo_Bar", "Foo_Bar",
]

# Stop words.
STOPS = [
    "the", "the the", "a b the", "the cat", "cat the", "the AND cat", "cat AND the", "the OR the", "the NEAR cat", "+the cat",
    "-the cat", "cat -the", "+the", "-the", "\"the cat\"", "\"cat the dog\"", "the-cat", "to be or not to be", "NOT the",
    "the NOT cat", "cat NOT the", "(the)", "(the cat)", "the*", "the~", "tHe", "The cat", "THE", "an apple a day", "is", "don't",
    "it's", "the's", "the the the", "the a an", "a the", "the cat the mat", "the cat AND the mat", "the OR cat", "cat OR the",
    "(the OR cat)", "the XOR cat", "cat XOR the", "title:the", "the:cat", "\"the\"", "\"the the\"", "the \"cat\"", "\"cat\" the",
    "the cat NEAR the mat", "the ADJ cat", "the NEAR/3 cat", "and the", "cat and the dog", "cat and dog", "not cat", "about cat",
    "cat about", "an", "an AND a", "a AND an", "a OR an", "a XOR an", "a NOT an", "+a +an", "-a -an", "+a -an", "a-an", "an-a",
    "it's the", "the's cat", "cat the's", "the.cat", "The.Cat", "A.B.C the", "the A.B.C", "the 1990s", "the c++", "the*cat",
    "the?cat", "s", "t", "i", "ab the", "the ab", "x the y", "the the cat", "cat the the", "the cat the", "both and",
    "c'est la vie", "o'clock the",
]
STOPS_ES = ["el gato", "el", "el AND gato", "gato el", "la casa de la monta\u00f1a", "para", "+el gato", "-el gato", "un gato y el perro"]
STOPS_FR = ["le chat", "le", "le AND chat", "l'homme", "qu'il", "le chat et la souris", "c'est la vie"]

# Misc: acronyms, long words, punctuation, quotes, tilde, empties, fallbacks, non-ASCII.
MISC = [
    "A.B.C", "A.B.C.", "a.b.c", "U.S.A", "U.S.A.", "U.S.A. today", "c++", "c#", "C++", "3.14", "1,000", "10:30", "$5.00", "5%",
    "1990s-era", "2020-01-02", "12-34", "a1b2", "1a", "a_b", "a_b_c", "_a", "a_", "__init__", "foo@bar.com", "http://x.com/a?b=1",
    "x.com", "a.b", "a. b", "a .b", "a . b", "...", ".", "..a", "a..", "a...b", "e.g.", "Ph.D.", "Ph.D", "p.m.", "a&b", "AT&T",
    "R&D", "a&&b", "a||b", "a & b", "!a", "a!", "a!b", "@a", "a@", "#a", "a#", "#hash", "#a#b", "$a", "a$", "%a", "a%", "=a", "a=b",
    "a=", "a==b", "^a", "a^2", "a^", "~a", "a~", "a~2", "a~0", "a~1", "a~3", "a~10", "a~-1", "a~x", "a ~2", "a~ b", "a~b", "a~~", "~",
    "~2", "a~2~3", "\"a b\"~3", "\"a b\" ~3", "\"a b\"~", "\"a b\"~0", "\"a b\"~x", "\"a b\"~10", "\"a b\"~2 c", "\"a b~3\"", "a~2 b~2",
    "a<b", "a>b", "<a>", "a[b]", "[a TO b]", "{a TO b}", "a:[b TO c]", "a..b", "1..10", "a{b}", "|a|", "`a`", "'a'", "'a b'",
    "\"a b", "a \"b", "a b\"", "\"", "\"\"", "\"\" a", "a \"\"", "\"a\"b\"", "\"\"a b\"\"", "\"a b\"\"c d\"", "\"a b\"c", "a\"b\"", "\"a\" \"b\"",
    "\"a b\" \"c", "\"a b\" c\"", "\"\"\"", "\"\"\"\"", "\"a\"\"", "'", "''", "\"'\"", "\"a 'b c' d\"", "\"a \\\" b\"", "a\\\"b", "\\", "a\\", "\\a",
    "a\\b", "a\\ b", "a \\b", "a\\\\b", "\\\"", "\\(", "a\\(b", "\\*", "a\\*", "a*\\", "\\+a", "\\-a", "\\AND", "a \\AND b", "\\:",
    "a\\:b", "title\\:a", "a:b:c", "a:", ":a", ":", "::", "a::b", "a: b", "a :b", "a : b", "title:", "title: a", "title:\"a b\"",
    "title:(a b)", "title:a title:b", "title:a:b", "title:a-b", "title:a.b", "title:+a", "+title:a", "-title:a", "title:-a", "Title:a",
    "TITLE:a", "title.field:a", "title_field:a", "title-field:a", "1:a", "a:1", "a:b c:d", "a:\"b c\" d", "http:", "http:x", "mailto:a@b.c",
    "", " ", "  ", "\t", "\n", " \t\n ", "  a  ", "\ta\t", "a\nb", "a\tb", "a\r\nb", "a\u00a0b", "a\u3000b", "a\u2003b", "a\u200bb", "a\u200db",
    "\u00ad", "a\u00adb", "\ufeffa", "a\ufeff", "\ufffd", "a\ufffdb", "\u0001", "a\u0001b", "a\u007fb", "a\u0085b",
    "caf\u00e9", "cafe\u0301", "na\u00efve", "\u00c9ric", "\u00e9ric", "\u00c9RIC", "\u0130stanbul", "i\u0307", "stra\u00dfe", "STRASSE", "\u00df", "\u1e9e",
    "\u03a3\u03af\u03c3\u03c5\u03c6\u03bf\u03c2", "\u0391\u0398\u0397\u039d\u0391", "\u0430\u0431\u0432", "\u0410\u0411\u0412", "\u05e9\u05dc\u05d5\u05dd", "\u0645\u0631\u062d\u0628\u0627", "\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35",
    "\u4e2d\u6587\u5206\u8bcd", "\u4e2d\u6587 \u5206\u8bcd", "\u4e2d\u6587a", "a\u4e2d\u6587", "a\u4e2d\u6587b", "\u4e2d\u6587AND\u5206\u8bcd", "\u4e2d\u6587 AND \u5206\u8bcd", "\"\u4e2d\u6587\u5206\u8bcd\"",
    "\u4e2d\u6587*", "\u4e2d*", "+\u4e2d\u6587", "-\u4e2d\u6587", "(\u4e2d\u6587)", "\u4e2d\u6587 NEAR \u5206\u8bcd", "\u4e2d\u6587-\u5206\u8bcd", "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8", "\u3072\u3089\u304c\u306a", "\u30ab\u30bf\u30ab\u30ca",
    "\ud55c\uad6d\uc5b4", "\ud55c\uad6d\uc5b4 \ud14c\uc2a4\ud2b8", "\U0001f600", "a\U0001f600b", "\U0001f468\u200d\U0001f469\u200d\U0001f467", "\U0001d400\U0001d401", "\U00020000\U00020001",
    "a" * 63, "a" * 64, "a" * 65, "a" * 70, "a" * 100, "a" * 245, "a" * 246, "a" * 300, "A" * 70, "ab " * 40, "a-" * 40 + "a", "a b " * 100,
    "\u00e9" * 40, "\u4e2d" * 30, ("ab" * 40) + " cd", "a" * 70 + "*", "a" * 70 + "~", "\"" + "a" * 70 + " b\"", "+" + "a" * 70, "x" * 63 + "-" + "y" * 63,
    "NOT", "NOT NOT", "xor", "OR", "a OR b OR c OR d OR e OR f OR g OR h", "a AND b AND c AND d AND e AND f AND g AND h",
    "the a an", "the the the the", "the AND a", "\"the a\"", "(the a)", "the* a*", "+the +a", "-the -a", "the NOT a", "the and a",
]

# Wildcard, partial and fuzzy syntax, as the user writes it (Xapiand's cleanup runs in `xapiand`).
STARS = [
    "ba*", "ba**", "ba", "ba?", "b?a", "b*a", "*ba", "?ba", "ba*c*", "*", "**", "***", "?", "??", "a*", "a**", "-ba*", "+ba*",
    "\"ba*\"", "ba* bc*", "ba*-bc", "ba.*", "b-*", "ba *", "ba * bc", "ba?*", "ba*?", "b?*", "ba**c", "ba*c", "ba?c", "b??a", "ba??",
    "*a", "a*b*c", "?*", "*?", "ba*bc*de", "ba* bc", "ba** bc", "ba bc*", "ba bc**", "ba bc", "title:ba*", "title:ba**", "ba*:", "ba*,",
    "ba*.", "ba.", "ba,", "ba-*", "ba_*", "ba'*", "ba\u00e9*", "\u00e9*", "\u4e2d*", "a1*", "1*", "_*", "baa", "baa*", "baa**", "ba*)",
    "(ba*", "(ba*)", "ba* AND bc*", "ba* OR bc*", "ba* NEAR bc*", "NOT ba*", "ba* NOT bc*", "ba* ADJ bc*", "ba* XOR bc", "ba*~", "ba~*",
    "ba~", "ba~1", "ba~2", "ba~3", "ba~10", "ba~0", "ba~-1", "ba~ bc~", "ba~2 bc", "ba~2 bc~1", "\"ba bc\"~2", "banna~ banana", "banna~",
    "banna~1", "banna~2", "banna~3", "banana~", "cabana~", "title:ba~", "title:banna~2", "-banna~", "+banna~", "\"banna~\"", "(banna~)",
    "banna~ OR banana~", "banna~ AND banana", "banna~ NEAR banana", "banna~ cabana~ obama~", "bann~a", "~banna", "banna~~", "banna~2~1",
]

# Expansion limits: partial (default 50, most frequent), wildcard (0), fuzzy (0).
EXPAND_PARTIAL = ["baa", "baa5", "ba", "b", "baa3", "obama", "oba", "the cat", "baa00", "ob", "ab", "abc", "abcd", "abcde"]
EXPAND_WILDCARD = ["baa*", "ba*", "baa0*", "baa?1", "b?a*", "ba?", "oba*", "ob?ma", "*aa05", "a*", "ab*", "baa[0-9]*", "banana*", "nomatch*"]
EXPAND_FUZZY = ["banna~", "banana~1", "banna~2", "obama~", "cabana~", "baa05~", "baa5~1", "xyz~", "ban~"]

PREFIX_QUERIES = ["obama", "Obama", "running", "Running", "title:obama", "foo:bar", "obama*", "ob?ma", "ob*ma", "obama~", "obama~2", "ob",
                  "\"a b\"", "a NEAR b", "+a -b", "a-b", "1990s-era", "caf\u00e9", "\u4e2d\u6587\u5206\u8bcd", "the", "a OR b", "(a b) c",
                  "Barack Obama's", "A.B.C", "the cat", "A b", "a B", "ABC", "e-mail", "3.14", "a:b", "obama running", "Z", "z"]
PREFIXES = ["S", "title.S", "a.b.S", "\x07\x12S", "x:S", "Xs", "XS", "Z", "z", ""]


def sample(lst, n):
    """n evenly spaced items of lst, deterministically."""
    if len(lst) <= n:
        return list(lst)
    return [lst[k * len(lst) // n] for k in range(n)]


def variants(group, queries, n=12, plain=4, extra_ops=("or",)):
    """The same queries under the other Xapiand configurations, on a sample."""
    each(group, sample(queries, n), ops=("unset",))
    each(group, sample(queries, n // 2), ops=extra_ops)
    each(group, sample(queries, n // 2), ops=("and",), stem="all_z")
    each(group, sample(queries, n // 2), ops=("and",), stem="unset", stop="")
    each(group, sample(queries, plain), ops=("near", "phrase", "max"))


_lo, _hi = MISC.index("caf\u00e9"), MISC.index("a" * 63)
MISC = [q for i, q in enumerate(MISC) if not _lo <= i < _hi or i % 2 == 0]


def main():
    # Base: the existing 22 queries over Xapiand's configurations.
    for op in ("unset", "and", "or"):
        for stem in ("unset", "some", "all_z"):
            each("base", BASE, ops=(op,), stem=stem)
        each("base", BASE, ops=("and",), stop="")
    for op in PLAIN_OPS:
        each("base", BASE, ops=(op,))

    # Item 1: precedence and flattening.
    each("precedence", PRECEDENCE, ops=("and",))
    variants("precedence", PRECEDENCE)

    # Item 2: + and -.
    each("plusminus", PLUSMINUS, ops=("and",))
    variants("plusminus", PLUSMINUS)

    # Item 3: NEAR and ADJ windows.
    each("near", NEARADJ, ops=("and",))
    variants("near", NEARADJ)
    each("near", NEARADJ_ALT, ops=("or", "unset", "near", "phrase", "max", "elite_set", "synonym"))
    each("near", NEARADJ_ALT, ops=("and",), stem="all_z")

    # Item 4: phrase generators.
    core = ["-", ":", "/", ".", "@", "\\", "_", ",", ";", "'", "&", "+", "#", "\u2019"]
    each("generator", ["ab{c}cd".format(c=c) for c in GEN_CHARS], ops=("and", "unset", "phrase"))
    each("generator", [s.format(c=c) for c in core for s in ("12{c}34", "Ab{c}Cd", "ab{c}", "{c}ab", "ab{c}cd{c}ef", "ab {c} cd")],
         ops=("and",))
    each("generator", ["ab{c}cd".format(c=c) for c in core] + ["ab{c}cd{c}ef".format(c=c) for c in core], ops=("and",), stem="all")
    each("generator", ["running{c}runners".format(c=c) for c in core] + ["Running{c}Runners".format(c=c) for c in core], ops=("and",))

    # Item 5: brackets.
    each("parens", PARENS, ops=("and",))
    variants("parens", PARENS)
    each("parens", sample(PARENS, 25), ops=("and",), extra=("partial",))
    each("parens", sample(PARENS, 25), ops=("and",), extra=("wildcard",))

    # Missing operands and operator keywords.
    each("operands", OPERANDS, ops=("and",))
    variants("operands", OPERANDS)
    for extra in (("partial",), ("wildcard",), ("wildcard", "partial"), ("wildcard", "wildcard_single", "wildcard_multi")):
        each("operands", sample(OPERANDS, 30), ops=("and",), extra=extra)
    each("operands", sample(OPERANDS, 20), ops=("and",), cjk=True)

    # Item 6: NEAR (and the other operators) under PARTIAL and its neighbours.
    each("partial", NEARADJ, ops=("and",), kind="partial")
    each("partial", sample(NEARADJ, 45), ops=("and",), kind="wildcard")
    each("partial", sample(NEARADJ, 20), ops=("and",), extra=("partial", "wildcard"))
    each("partial", sample(NEARADJ, 20), ops=("and",), extra=("partial", "wildcard", "wildcard_single", "wildcard_multi"))
    each("partial", sample(NEARADJ, 10), ops=("or", "unset", "near", "phrase", "max"), kind="partial")
    each("partial", sample(PRECEDENCE, 15), ops=("and",), kind="partial")
    each("partial", sample(PLUSMINUS, 15), ops=("and",), kind="partial")
    each("partial", sample(PARENS, 15), ops=("and",), kind="partial")
    each("partial", sample(NEARADJ, 12), ops=("and",), kind="partial", stem="unset", stop="")
    each("partial", sample(NEARADJ, 8), ops=("and",), kind="partial", cjk=True)

    # Stemming and capital letters.
    each("stemming", STEMMING, ops=("and",))
    variants("stemming", STEMMING, n=16)
    each("stemming", sample(STEMMING, 30), ops=("unset",), stem="all")
    each("stemming", sample(STEMMING, 20), ops=("unset",), kind="partial")

    # Stop words.
    each("stopwords", STOPS, ops=("and",))
    variants("stopwords", STOPS, n=16)
    for strategy in ("none", "all", "stemmed"):
        each("stopwords", sample(STOPS, 24), ops=("and",), stop_strategy=strategy)
    each("stopwords", sample(STOPS, 24), ops=("and",), stem="all_z", stop_strategy="all")
    each("stopwords", sample(STOPS, 14), ops=("unset",), kind="partial")
    each("stopwords", sample(STOPS, 14), ops=("and",), kind="wildcard")
    for op in ("unset", "and"):
        each("stopwords", STOPS_ES, ops=(op,), stem="some", lang="spanish", stop="es")
        each("stopwords", STOPS_FR, ops=(op,), stem="some", lang="french", stop="fr")

    # Miscellany.
    each("misc", MISC, ops=("and",))
    variants("misc", MISC, n=12)
    each("misc", [q for q in MISC if any(ord(ch) > 0x2e80 for ch in q)], ops=("and", "unset"), cjk=True)
    each("misc", sample(MISC, 6), ops=("unset",), extra=("word_breaks",))
    each("misc", sample(MISC, 20), ops=("and",), kind="partial")

    # Wildcards, partial, fuzzy.
    each("stars", STARS, ops=("and",), kind="plain")
    each("stars", sample(STARS, 30), ops=("unset",), kind="plain")
    for kind in ("wildcard", "partial", "fuzzy"):
        each("stars", sample(STARS, 24), ops=("and",), kind=kind)
    each("stars", sample(STARS, 16), ops=("or",), kind="plain")
    each("stars", sample(STARS, 16), ops=("and",), kind="plain", stem="all_z")
    each("stars", sample(STARS, 16), ops=("and",), kind="plain", stem="unset", stop="")
    each("stars", sample(STARS, 15), ops=("near", "phrase"), kind="plain")
    each("stars", sample(STARS, 12), ops=("and",), kind="plain", cjk=True)

    # Prefixes.
    pq = sample(PREFIX_QUERIES, 18)
    for prefix in ("S", "title.S", "a.b.S", "\x07\x12S", ""):
        each("prefix", pq, ops=("and",), prefix=prefix)
    for prefix in ("S", "title.S"):
        each("prefix", pq, ops=("unset",), prefix=prefix)
    for kind in ("wildcard", "partial", "fuzzy"):
        each("prefix", pq, ops=("and",), kind=kind, prefix="title.S")
    each("prefix", pq, ops=("and",), prefix="title.S", stem="all_z")
    each("prefix", pq, ops=("near", "phrase"), prefix="title.S")

    # Expansion limits, hit and not hit. The database holds baa00..baa59 under "", "S" and "title.S".
    xp = dict(ops=("and",), stem="unset", stop="", expand=1)
    for max_n in (0, 1, 5, 50):
        for limit in ("error", "first", "most_frequent"):
            each("expand", EXPAND_PARTIAL[:7], kind="partial", prefix="", partial_max=max_n, partial_limit=limit, **xp)
            each("expand", EXPAND_PARTIAL[:2], kind="partial", prefix="title.S", partial_max=max_n, partial_limit=limit, **xp)
    for max_n in (0, 3, 60, 61):
        for limit in ("error", "first", "most_frequent"):
            each("expand", EXPAND_WILDCARD[:8], kind="plain", prefix="", wildcard_max=max_n, wildcard_limit=limit, **xp)
            each("expand", EXPAND_WILDCARD[:2], kind="plain", prefix="title.S", wildcard_max=max_n, wildcard_limit=limit, **xp)
    for max_n in (0, 3):
        for limit in ("error", "first", "most_frequent"):
            each("expand", EXPAND_FUZZY[:6], kind="plain", prefix="", fuzzy_max=max_n, fuzzy_limit=limit, **xp)
            each("expand", EXPAND_FUZZY[:1], kind="plain", prefix="title.S", fuzzy_max=max_n, fuzzy_limit=limit, **xp)
    # Xapiand's own settings (partial 50 most frequent, the rest unlimited) with stemming and a stopper on.
    for prefix in ("", "title.S"):
        each("expand", EXPAND_PARTIAL, ops=("and", "unset"), kind="partial", prefix=prefix, expand=1)
        each("expand", EXPAND_WILDCARD, ops=("and",), kind="plain", prefix=prefix, expand=1)
        each("expand", EXPAND_FUZZY, ops=("and",), kind="plain", prefix=prefix, expand=1)
        each("expand", EXPAND_FUZZY[:5], ops=("and",), kind="fuzzy", prefix=prefix, expand=1)

    sys.stdout.write("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
