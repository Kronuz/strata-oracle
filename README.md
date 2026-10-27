# strata-oracle

GPL-side harnesses for strata, kept out of the strata repository and never shipped
with it. It holds the Xapian baseline engine for the search-benchmark-game protocol
and, later, the programs that record Xapian behavior as test vectors for strata's
clean-room compatibility work.

Everything here links Xapian (GPL-2.0-or-later) and is licensed accordingly.

## Vectors

`vectors/oracle` records Xapian behavior as JSON lines:

- `termgen TEXTS`: terms, wdf, and positions per stemming strategy, with and without
  CJK n-grams.
- `parse QUERIES`: query descriptions per flag set and stemming strategy.
- `stem LANGUAGE WORDS`: stems.
- `rank CORPUS N QUERIES`: an in-memory index of N benchmark documents, then top-10
  weights (17 significant digits), percents, and match bounds for check_at_least 0,
  100, and the document count.

Inputs live in `vectors/inputs/`. Vectors are recorded with Xapian 2.1.0; Xapiand
vendors a 2.0.0 fork whose weighting, term generation, and parsing match it for these
inputs unless a vector notes otherwise.

## parse-v2

`vectors/out/parse-v2.jsonl` (3,488 rows) records the `QueryParser` configurations Xapiand
can produce for a `text` field, from `src/query_dsl.cc` (`get_term_query`) and
`src/engine/xapian/query.cc` (`parse_text`). Regenerate with
`vectors/gen-parse-v2.py > vectors/inputs/parse-v2.tsv` and
`oracle parse-v2 inputs/parse-v2.tsv inputs/stopwords > out/parse-v2.jsonl`; two runs are
byte-identical.

Each row has the shape of `parse.jsonl` (`query`, `flags`, `stem`, `description`, `error`) plus
the settings it was parsed under:

| Field | Meaning |
|---|---|
| `group` | The set of rows a behaviour is pinned by (below) |
| `query` | The string handed to Xapian, after Xapiand's own cleanup (trailing `*`/`**` handling, the `*` appended to a `_wildcard` word, `~` appended per word for `_fuzzy`) |
| `flags` | PHRASE, LOVEHATE and FUZZY always; BOOLEAN only when the default operator is `and` or `or`; WILDCARD, WILDCARD_SINGLE and WILDCARD_MULTI, PARTIAL and CJK_NGRAM as Xapiand sets them |
| `default_op` | `unset` (Xapian's OR), `and`, `or`, `near`, `phrase`, `elite_set`, `synonym`, `max`; the last five set no stopper and no stemmer, as Xapiand does |
| `stopper`, `stop_strategy` | `none` or the language list (`inputs/stopwords/`, copied from Xapiand's `stopwords/`); `default` leaves Xapian's STOP_STEMMED |
| `stem_lang`, `stem` | `stem: unset` means no stemmer; otherwise `Xapian::Stem(stem_lang)` with `none`, `some`, `all` or `all_z` |
| `prefix` | The default prefix passed to `parse_query` (field prefix plus the type character `S`) |
| `partial_max`, `partial_limit`, `fuzzy_max`, `fuzzy_limit`, `wildcard_max`, `wildcard_limit` | `set_max_expansion` per flag; Xapiand uses 50 most_frequent, 0 error, 0 error |
| `error`, `error_type` | The message and Xapian exception type when parsing raised |
| `expanded` | Only on `group: expand`: the terms the query matched in the fixed expansion database, or the error that matching raised |

The expansion database holds `baa00` to `baa59` (document frequency `1 + (j * 37 % 11)`) and 31
other words (frequency 2; `obamas` is listed twice, so 4), each indexed bare, with the prefix `S` and with `title.S`. It is built
by `expansion_db()` in `oracle.cc`.

Groups and the queryparser design items they pin:

| Group | Rows | Pins |
|---|---|---|
| `base` | 330 | The 22 queries of `inputs/queries.txt` over every default operator, stem strategy, with and without the stopper, with and without BOOLEAN |
| `precedence` | 103 | Item 1: juxtaposition against OR/AND/XOR/NOT/NEAR, chain and bracket flattening |
| `plusminus` | 105 | Item 2: `+a b`, `+a -b c`, lone `-a`, `+`/`-` on phrases and brackets |
| `near` | 202 | Item 3: NEAR/ADJ and `/n` windows for 2, 3, 4 and more terms, mixed chains, bad `n` |
| `generator` | 275 | Item 4: `- : / . @ \` and 30 other characters between word characters, at word edges, with stemming |
| `parens` | 172 | Item 5: unclosed `(`, stray `)`, empty brackets, 1,000-deep nesting, with and without BOOLEAN |
| `operands` | 282 | Item 5: missing operands and operator spellings; the error text per operator |
| `partial` | 286 | Item 6: the same operator inputs under PARTIAL, WILDCARD and both, to separate the rows that reparse from those that raise |
| `stemming` | 183 | Item 7: `obam*`, capitals, `'s`, apostrophes, accents under every stem strategy |
| `stopwords` | 299 | Stoppers on and off, STOP_NONE/ALL/STEMMED, stop words beside operators, `+`, `-`, phrases, all-stop-word texts; Spanish and French lists |
| `misc` | 368 | Acronyms, `c++`, `3.14`, 63 to 300-byte words, quotes, `~`, backslash, empty and whitespace texts, non-ASCII, CJK with and without CJK_NGRAM, WORD_BREAKS |
| `stars` | 279 | `*`, `**`, `?`, `~`, `~n` as Xapiand rewrites them, for each DSL node kind |
| `prefix` | 232 | Default prefixes `S`, `title.S`, `a.b.S`, a binary prefix and none, against capitals, stemming, wildcards, phrases |
| `expand` | 372 | Partial, wildcard and fuzzy expansion limits hit and not hit, each limit type |

Notes on what the rows show for Xapian 2.1.0 under Xapiand's settings:

- FLAG_WORD_BREAKS raises `FLAG_WORD_BREAKS requires building Xapian to use ICU` in this
  build (6 rows); Xapiand sets it only with ICU, so those rows are unreachable here.
- `OP_NEAR and OP_PHRASE only currently support leaf subqueries` is raised (26 rows) when
  NEAR or ADJ meets a bracket or a composite operand.
- A stemmed term carries `Z` before the field prefix (`ZSa`).
