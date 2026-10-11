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
