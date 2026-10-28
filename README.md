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

## parse-v3

`vectors/out/parse-v3.jsonl` (1,995 rows) records variations of the query shapes the queryparser's T2 run
against parse-v2 still fails (the `open` rows of its `EXCEPTIONS-v2.md`), and the four open shapes of CR2
(`a OR -b`, `a XOR -b`, `a AND NOT -b`, `a AND --b`). Regenerate with
`vectors/gen-parse-v3.py > vectors/inputs/parse-v3.tsv` and
`oracle parse-v2 inputs/parse-v3.tsv inputs/stopwords > out/parse-v3.jsonl`; two runs are byte-identical.
The rows have parse-v2's shape and the same settings fields; the query is never rewritten (no trailing `*`
handling), so `query` is exactly what the parser saw.

Each group is one shape: a primary template over every operand pattern and configuration, then a few
neighbouring templates (another position, operator or sign) over the all-stop and all-non-stop patterns. One
factor changes between neighbouring rows:

| Factor | Values |
|---|---|
| Operands | `a b c d` (single-letter stop words), `foo bar baz qux` (non-stop), one stop word in each position; `the an of is` (ordinary stop words) for the single-operand shapes |
| Default operator | `and`, `or`, `unset` (Xapian's OR); `near` and `phrase` where noted |
| BOOLEAN | on with `and`/`or`; absent with `and`; present with `unset` |
| Flags | none extra, `partial`, `wildcard`, `wildcard`+`wildcard_multi`+`wildcard_single` (any query holding `*`), `cjk_ngram`, `pure_not`, `boolean_any_case`, LOVEHATE off |
| Stopper | `en` (STOP_STEMMED), none, STOP_ALL, STOP_NONE |
| Stemmer | STEM_SOME (Xapiand), none, STEM_ALL_Z |
| Prefix | `S`; `title.S` for the `~` shapes |

Groups (shape, rows). A `-forms` group holds the same CR2 shape in other forms (more terms, a phrase, a
bracket, a missing operand):

| Group | Rows |
|---|---|
| `close-after` | 40 |
| `close-group` | 40 |
| `close-lead-star` | 33 |
| `open-glued` | 40 |
| `open-nested` | 40 |
| `open-quote` | 36 |
| `near-paren` | 40 |
| `near-paren-mixed` | 40 |
| `glued-call` | 40 |
| `glued-call-tail` | 40 |
| `near-quote-left` | 40 |
| `near-quote-right` | 40 |
| `near-quote-both` | 40 |
| `near-plus` | 40 |
| `near-plus-left` | 40 |
| `plus-ops` | 40 |
| `near-plus-star` | 42 |
| `near-trail` | 33 |
| `near-lead-star` | 35 |
| `near-only` | 15 |
| `near-twice` | 40 |
| `near-hyphen-star` | 44 |
| `near-quote-star` | 46 |
| `near-dotted-star` | 38 |
| `near-win-and` | 40 |
| `near-win-bool` | 40 |
| `near-win-and-trail` | 33 |
| `minus-quote` | 40 |
| `minus-group` | 40 |
| `minus-lead-or` | 40 |
| `minus-last` | 40 |
| `minus-first` | 40 |
| `minus-last-of-4` | 40 |
| `minus-and` | 40 |
| `stop-minus` | 36 |
| `stop-minus-two` | 38 |
| `cr2-or-minus` | 44 |
| `cr2-or-minus-forms` | 44 |
| `cr2-xor-minus` | 44 |
| `cr2-xor-minus-forms` | 44 |
| `cr2-and-not-minus` | 44 |
| `cr2-and-not-minus-forms` | 48 |
| `cr2-and-doubleminus` | 44 |
| `cr2-and-doubleminus-forms` | 44 |
| `tilde-minus-digit` | 40 |
| `tilde-star-or` | 44 |
| `tilde-digit-star` | 44 |
| `backslash-open` | 44 |
| `cjk-op` | 30 |
| `cjk-phrase` | 48 |

## shards

`vectors/out/shards-<config>.jsonl` (six configurations, 44 queries each) records several shards
searched as one `Xapian::Database` (`add_database` per shard, in shard order, glass backend on disk).
Regenerate with `vectors/gen-shards.py vectors/inputs` and
`oracle shards inputs/shards-<config>.jsonl inputs/shards-queries.txt DIR > out/shards-<config>.jsonl`
(`DIR` holds the shards' glass directories); two runs are byte-identical.

Inputs: `inputs/shards-<config>.jsonl` has `{"shards":S}` then one line per document
(`shard`, local `did` with gaps, `key` in hex, `terms` in order). Configurations `s1`, `s2`, `s3`, `s5`,
`s5e` (shards 0 and 3 stay empty) and `s7` (half of the documents in shard 0). Keys are short byte
strings with many ties, some empty, some holding 0x00 and 0xff, in value slot 0.

Rows: the first is the index (`docs`, `avlength`, `lastdocid`, the document-length bounds, and each
shard's `docs` and `lastdocid`); then `termfreq` and `collfreq` for `w0` to `w39` and a term nothing has;
then, per query (`TERM`, `OR`, `AND`, `AND_MAYBE`, `AND_NOT`, `PHRASE`) and mode, the top 25 as
`[docid, weight]` with the match bounds at `check_at_least` 0 and at the document count (relevance
and key modes; the others at the count only). Modes: `rel`, `rel-desc` (`set_docid_order(DESCENDING)`),
`key` (`set_sort_by_key_then_relevance(key maker, false)`), `key-desc` and `key-rev` (`reverse` true).

What the rows show for Xapian 2.1.0:

- A hit's docid is `(did - 1) * shards + shard + 1`; the database's `lastdocid` is the largest of those over
  the shards that ever gave a docid; empty shards keep their slot in the numbering.
- Statistics are the shards' together: `docs`, `avlength` and every term's `termfreq` are sums; weights
  are the single-database weights.
- The document-length bounds of the glass backend are exact (the shortest and longest document of the
  non-empty shards); empty shards do not lower them.
- `key` sorts ascending by memcmp of the key; equal keys by weight, descending; equal weights by docid
  (ascending, or descending under `key-desc`). `key-rev` reverses the key order only: weights still
  descend within a key.
- At `check_at_least` equal to the document count, `lower`, `estimated` and `upper` meet at the number of
  matches, in every mode.
