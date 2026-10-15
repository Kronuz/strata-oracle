// Records Xapian's observable behavior as JSON-lines test vectors for strata's
// clean-room compatibility work. GPL (links Xapian); never shipped with strata.
//
//   oracle termgen  TEXTS_FILE             one text per line -> terms, wdf, positions per stem strategy
//   oracle unicode                         every code point's category and lowercase mapping
//   oracle chars                           how TermGenerator treats each code point, as ranges
//   oracle infix                           non-word code points that do not just split words
//   oracle termgen-xapiand TEXTS_FILE      prefixes, wdf increments, stoppers, positionless indexing
//   oracle parse    QUERIES_FILE           one query per line -> descriptions per flag set
//   oracle stem     LANGUAGE WORDS_FILE    one word per line -> stem
//   oracle languages                       the stemmer languages, one per line
//   oracle rank     CORPUS_JSON N QUERIES  index N docs, then top-10 weights, percents, estimates
//   oracle termgen-bench CORPUS_JSON N     TermGenerator throughput into Xapian::Document
#include <xapian.h>

#include <chrono>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <random>
#include <string>
#include <vector>

namespace {

std::string json_string(const std::string& s) {
	std::string out = "\"";
	for (unsigned char c : s) {
		switch (c) {
		case '"': out += "\\\""; break;
		case '\\': out += "\\\\"; break;
		case '\n': out += "\\n"; break;
		case '\t': out += "\\t"; break;
		default:
			if (c < 0x20) {
				char buf[8];
				std::snprintf(buf, sizeof buf, "\\u%04x", c);
				out += buf;
			} else {
				out += char(c);
			}
		}
	}
	return out + "\"";
}

std::vector<std::string> lines(const char* path) {
	std::ifstream in(path);
	std::vector<std::string> out;
	for (std::string line; std::getline(in, line);) {
		if (!line.empty()) { out.push_back(line); }
	}
	return out;
}

std::string terms_json(const Xapian::Document& doc) {
	std::string out = "[";
	bool first = true;
	for (auto t = doc.termlist_begin(); t != doc.termlist_end(); ++t) {
		if (!first) { out += ","; }
		first = false;
		out += "[" + json_string(*t) + "," + std::to_string(t.get_wdf()) + ",[";
		bool fp = true;
		for (auto p = t.positionlist_begin(); p != t.positionlist_end(); ++p) {
			if (!fp) { out += ","; }
			fp = false;
			out += std::to_string(*p);
		}
		out += "]]";
	}
	return out + "]";
}

// Configurations Xapiand passes to TermGenerator: prefixes, wdf increments, stop
// strategies with a stopper, and positionless indexing.
int termgen_xapiand(const char* path) {
	Xapian::SimpleStopper stopper;
	for (const char* w : {"the", "a", "an", "and", "of", "to", "in", "is", "it", "over"}) { stopper.add(w); }
	struct config {
		const char* name;
		const char* prefix;
		Xapian::termcount wdf_inc;
		bool positions;
		Xapian::TermGenerator::stop_strategy stop;
		Xapian::TermGenerator::stem_strategy stem;
		bool stemmer = true;
	};
	const config configs[] = {
		{"prefix", "XA", 1, true, Xapian::TermGenerator::STOP_NONE, Xapian::TermGenerator::STEM_NONE},
		{"wdf_inc_3", "", 3, true, Xapian::TermGenerator::STOP_NONE, Xapian::TermGenerator::STEM_NONE},
		{"positionless", "XB", 2, false, Xapian::TermGenerator::STOP_NONE, Xapian::TermGenerator::STEM_SOME},
		{"stop_all", "", 1, true, Xapian::TermGenerator::STOP_ALL, Xapian::TermGenerator::STEM_SOME},
		{"stop_stemmed", "", 1, true, Xapian::TermGenerator::STOP_STEMMED, Xapian::TermGenerator::STEM_SOME},
		{"stop_none_stopper", "", 1, true, Xapian::TermGenerator::STOP_NONE, Xapian::TermGenerator::STEM_SOME},
		{"all_stop_stemmed", "", 1, true, Xapian::TermGenerator::STOP_STEMMED, Xapian::TermGenerator::STEM_ALL},
		{"all_stop_all", "", 1, true, Xapian::TermGenerator::STOP_ALL, Xapian::TermGenerator::STEM_ALL},
		{"all_z_stop_stemmed", "XC", 1, true, Xapian::TermGenerator::STOP_STEMMED, Xapian::TermGenerator::STEM_ALL_Z},
		{"nostem_some", "", 1, true, Xapian::TermGenerator::STOP_STEMMED, Xapian::TermGenerator::STEM_SOME, false},
		{"nostem_all", "", 1, true, Xapian::TermGenerator::STOP_STEMMED, Xapian::TermGenerator::STEM_ALL, false},
		{"nostem_all_z", "", 1, true, Xapian::TermGenerator::STOP_ALL, Xapian::TermGenerator::STEM_ALL_Z, false},
		{"defaults", "", 1, true, Xapian::TermGenerator::STOP_STEMMED, Xapian::TermGenerator::STEM_SOME, false},
	};
	for (const auto& text : lines(path)) {
		for (const auto& c : configs) {
			Xapian::TermGenerator g;
			if (std::string(c.name) != "defaults") {
				if (c.stemmer) { g.set_stemmer(Xapian::Stem("english")); }
				g.set_stemming_strategy(c.stem);
				g.set_stopper(&stopper);
				g.set_stopper_strategy(c.stop);
			}
			Xapian::Document doc;
			g.set_document(doc);
			if (c.positions) {
				g.index_text(text, c.wdf_inc, c.prefix);
			} else {
				g.index_text_without_positions(text, c.wdf_inc, c.prefix);
			}
			std::cout << "{\"text\":" << json_string(text) << ",\"config\":\"" << c.name << "\",\"prefix\":" << json_string(c.prefix)
			          << ",\"stem\":" << c.stem << ",\"stop\":" << c.stop << ",\"stemmer\":" << (c.stemmer ? "true" : "false") << ",\"wdf_inc\":" << c.wdf_inc << ",\"positions\":" << (c.positions ? "true" : "false") << ",\"termpos\":" << g.get_termpos() << ",\"terms\":" << terms_json(doc) << "}\n";
		}
	}
	return 0;
}

// Every assigned code point's general category and lowercase mapping, as Xapian's public
// Unicode API reports them (pins Xapian's Unicode tables, whatever version they are).
int unicode_table() {
	for (unsigned cp = 0; cp <= 0x10FFFF; ++cp) {
		const int category = int(Xapian::Unicode::get_category(cp));
		const unsigned lower = Xapian::Unicode::tolower(cp);
		if (category == int(Xapian::Unicode::UNASSIGNED) && lower == cp) { continue; }
		std::cout << cp << ' ' << category << ' ' << lower << '\n';
	}
	return 0;
}

// Indexes each code point doubled ("cc") with FLAG_CJK_NGRAM: no terms means not a word
// character, one term "cc" a word character, unigram plus bigram a CJK character. Prints
// "first last class" ranges with class none, word, or cjk.
int chars() {
	const char* names[] = {"none", "word", "cjk", "other"};
	int run_class = -1;
	unsigned run_first = 0;
	auto flush = [&](unsigned last) {
		if (run_class >= 0) { std::cout << run_first << ' ' << last << ' ' << names[run_class] << '\n'; }
	};
	for (unsigned cp = 0; cp <= 0x10FFFF; ++cp) {
		int cls;
		if (cp >= 0xD800 && cp <= 0xDFFF) {
			cls = 0;
		} else {
			std::string one, two;
			Xapian::Unicode::append_utf8(one, cp);
			two = one + one;
			Xapian::TermGenerator g;
			g.set_flags(Xapian::TermGenerator::FLAG_CJK_NGRAM);
			Xapian::Document doc;
			g.set_document(doc);
			g.index_text(two);
			const auto n = doc.termlist_count();
			if (n == 0) {
				cls = 0;
			} else if (n == 1) {
				cls = 1;
			} else if (n == 2) {
				cls = 2;
			} else {
				cls = 3;
			}
		}
		if (cls != run_class) {
			flush(cp - 1);
			run_class = cls;
			run_first = cp;
		}
	}
	flush(0x10FFFF);
	return 0;
}

std::string termset(const std::string& text) {
	Xapian::TermGenerator g;
	Xapian::Document doc;
	g.set_document(doc);
	g.index_text(text);
	std::string out;
	for (auto t = doc.termlist_begin(); t != doc.termlist_end(); ++t) { out += (out.empty() ? "" : " ") + *t; }
	return out;
}

// For each non-word code point c: the terms of "LcR" for letter/digit contexts, of "Cc ",
// "Cccc " and "Ccccc " (suffixes), and of "AcBc " (acronyms), printed when any of them
// is not the plain split. Then, for each word character w, whether "w.w." is an acronym.
int infix() {
	const std::pair<std::string, std::string> contexts[] = {{"a", "b"}, {"1", "2"}, {"a", "1"}, {"1", "a"}, {"A", "B"}};
	for (unsigned cp = 0; cp <= 0x10FFFF; ++cp) {
		if (cp >= 0xD800 && cp <= 0xDFFF) { continue; }
		std::string c;
		Xapian::Unicode::append_utf8(c, cp);
		if (!termset(c + c).empty()) { continue; }  // a word character
		std::string line;
		for (const auto& [l, r] : contexts) { line += " [" + termset(l + c + r) + "]"; }
		for (int n : {1, 3, 4}) {
			std::string w = "C";
			for (int i = 0; i < n; ++i) { w += c; }
			line += " [" + termset(w + " ") + "]";
		}
		line += " [" + termset("A" + c + "B" + c + " ") + "]";
		const bool interesting = line != " [a b] [1 2] [1 a] [1 a] [a b] [c] [c] [c] [a b]";
		if (interesting) { std::cout << "nonword " << cp << line << '\n'; }
	}
	for (unsigned cp = 0; cp <= 0x10FFFF; ++cp) {
		if (cp >= 0xD800 && cp <= 0xDFFF) { continue; }
		std::string c;
		Xapian::Unicode::append_utf8(c, cp);
		if (termset(c + c).empty()) { continue; }
		std::string lower;
		Xapian::Unicode::append_utf8(lower, Xapian::Unicode::tolower(cp));
		if (termset(c + "." + c + ".") == lower + lower) { std::cout << "acronym " << cp << '\n'; }
	}
	return 0;
}

int termgen(const char* path) {
	const std::pair<const char*, Xapian::TermGenerator::stem_strategy> strategies[] = {
		{"none", Xapian::TermGenerator::STEM_NONE}, {"some", Xapian::TermGenerator::STEM_SOME},
		{"all", Xapian::TermGenerator::STEM_ALL}, {"all_z", Xapian::TermGenerator::STEM_ALL_Z}};
	for (const auto& text : lines(path)) {
		for (const auto& [name, strategy] : strategies) {
			for (bool cjk : {false, true}) {
				Xapian::TermGenerator g;
				g.set_stemmer(Xapian::Stem("english"));
				g.set_stemming_strategy(strategy);
				if (cjk) { g.set_flags(Xapian::TermGenerator::FLAG_CJK_NGRAM); }
				Xapian::Document doc;
				g.set_document(doc);
				g.index_text(text);
				std::cout << "{\"text\":" << json_string(text) << ",\"stem\":\"" << name << "\",\"cjk_ngram\":" << (cjk ? "true" : "false")
				          << ",\"termpos\":" << g.get_termpos() << ",\"terms\":" << terms_json(doc) << "}\n";
			}
		}
	}
	return 0;
}

int parse(const char* path) {
	using QP = Xapian::QueryParser;
	const std::pair<const char*, unsigned> flag_sets[] = {
		{"default", QP::FLAG_DEFAULT},
		{"boolean|phrase|lovehate", QP::FLAG_BOOLEAN | QP::FLAG_PHRASE | QP::FLAG_LOVEHATE},
		{"default|wildcard|partial", QP::FLAG_DEFAULT | QP::FLAG_WILDCARD | QP::FLAG_PARTIAL},
		{"default|fuzzy", QP::FLAG_DEFAULT | QP::FLAG_FUZZY},
		{"default|boolean_any_case|pure_not", QP::FLAG_DEFAULT | QP::FLAG_BOOLEAN_ANY_CASE | QP::FLAG_PURE_NOT},
		{"default|cjk_ngram", QP::FLAG_DEFAULT | QP::FLAG_CJK_NGRAM},
	};
	const std::pair<const char*, QP::stem_strategy> strategies[] = {{"none", QP::STEM_NONE}, {"some", QP::STEM_SOME}, {"all", QP::STEM_ALL}, {"all_z", QP::STEM_ALL_Z}};
	Xapian::WritableDatabase db(std::string(), Xapian::DB_BACKEND_INMEMORY);  // for wildcard/partial expansion
	for (const auto& q : lines(path)) {
		for (const auto& [fname, flags] : flag_sets) {
			for (const auto& [sname, strategy] : strategies) {
				QP parser;
				parser.set_stemmer(Xapian::Stem("english"));
				parser.set_stemming_strategy(strategy);
				parser.set_database(db);
				std::string description, error;
				try {
					description = parser.parse_query(q, flags).get_description();
				} catch (const Xapian::QueryParserError& e) {
					error = e.get_msg();
				}
				std::cout << "{\"query\":" << json_string(q) << ",\"flags\":\"" << fname << "\",\"stem\":\"" << sname << "\",\"description\":"
				          << json_string(description) << ",\"error\":" << json_string(error) << "}\n";
			}
		}
	}
	return 0;
}

int stem(const char* language, const char* path) {
	Xapian::Stem stemmer(language);
	for (const auto& w : lines(path)) {
		std::cout << "{\"language\":" << json_string(language) << ",\"word\":" << json_string(w) << ",\"stem\":" << json_string(stemmer(w)) << "}\n";
	}
	return 0;
}

std::string text_field(const std::string& line) {
	auto at = line.find("\"text\": \"");
	if (at == std::string::npos) { return {}; }
	at += 9;
	return line.substr(at, line.find('"', at) - at);
}

int rank(const char* corpus, std::size_t n, const char* queries_path) {
	Xapian::WritableDatabase db(std::string(), Xapian::DB_BACKEND_INMEMORY);
	{
		std::ifstream in(corpus);
		std::string line;
		Xapian::TermGenerator g;
		for (std::size_t i = 0; i < n && std::getline(in, line); ++i) {
			Xapian::Document doc;
			g.set_document(doc);
			g.index_text(text_field(line));
			db.add_document(doc);
		}
		db.commit();
	}
	std::cout << "{\"index\":{\"docs\":" << db.get_doccount() << ",\"avlength\":" << db.get_avlength() << "}}\n";
	Xapian::QueryParser parser;
	parser.set_database(db);
	Xapian::Enquire enquire(db);
	for (const auto& q : lines(queries_path)) {
		Xapian::Query query = parser.parse_query(q, Xapian::QueryParser::FLAG_DEFAULT);
		enquire.set_query(query);
		for (Xapian::doccount check : {0u, 100u, db.get_doccount()}) {
			Xapian::MSet mset = enquire.get_mset(0, 10, check);
			std::cout << "{\"query\":" << json_string(q) << ",\"description\":" << json_string(query.get_description()) << ",\"check_at_least\":" << check
			          << ",\"lower\":" << mset.get_matches_lower_bound() << ",\"estimated\":" << mset.get_matches_estimated()
			          << ",\"upper\":" << mset.get_matches_upper_bound() << ",\"hits\":[";
			bool first = true;
			for (auto m = mset.begin(); m != mset.end(); ++m) {
				char weight[64];
				std::snprintf(weight, sizeof weight, "%.17g", m.get_weight());
				std::cout << (first ? "" : ",") << "[" << *m << "," << weight << "," << m.get_percent() << "]";
				first = false;
			}
			std::cout << "]}\n";
		}
	}
	return 0;
}

int termgen_bench(const char* corpus, std::size_t n) {
	std::vector<std::string> docs;
	std::size_t bytes = 0;
	std::ifstream in(corpus);
	for (std::string line; docs.size() < n && std::getline(in, line);) {
		docs.push_back(text_field(line));
		bytes += docs.back().size();
	}
	for (bool some : {false, true}) {
		double best = 1e300;
		std::size_t terms = 0;
		for (int trial = 0; trial < 3; ++trial) {
			terms = 0;
			auto t0 = std::chrono::steady_clock::now();
			for (const auto& d : docs) {
				Xapian::TermGenerator g;
				if (some) { g.set_stemmer(Xapian::Stem("english")); }
				Xapian::Document doc;
				g.set_document(doc);
				g.index_text(d);
				terms += doc.termlist_count();
			}
			best = std::min(best, std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count());
		}
		std::printf("%s: %zu docs, %.1f MB, %zu distinct terms per doc summed, %.1f MB/s\n", some ? "stem_some" : "stem_none", docs.size(), bytes / 1e6, terms, bytes / 1e6 / best);
	}
	return 0;
}

// Phase 4's vectors: a seeded structured corpus, written out in plain JSON so strata's
// tests rebuild it without sortable_serialise, then Xapian's answers over it: value
// ranges, sorts by value and by a multi-key with docid ties, collapse with its counts and
// both estimate triples, MatchSpy counts per check_at_least, and percent with a scored
// value source.
int values(std::size_t n) {
	std::mt19937_64 random(4);
	Xapian::WritableDatabase db(std::string(), Xapian::DB_BACKEND_INMEMORY);
	const char* categories[] = {"alpha", "beta", "gamma", "delta", "epsilon"};
	for (std::size_t i = 0; i < n; ++i) {
		Xapian::Document doc;
		std::vector<int> words;
		// Term ids skewed toward small ones, so some terms are frequent.
		for (unsigned k = 0, len = 5 + random() % 11; k < len; ++k) { words.push_back(int(random() % (1 + random() % 50))); }
		const auto price = std::int64_t(random() % 2001) - 1000;
		const double rating = double(random() % 1000001) / 1000.0 - 500.0;
		const char* category = categories[random() % 5];
		const double date = 1.6e9 + double(random() % 100000000);
		Xapian::termpos pos = 0;
		std::cout << "{\"doc\":" << i + 1 << ",\"terms\":[";
		for (std::size_t k = 0; k < words.size(); ++k) {
			doc.add_posting("w" + std::to_string(words[k]), ++pos);
			std::cout << (k ? "," : "") << json_string("w" + std::to_string(words[k]));
		}
		char r[64]; std::snprintf(r, sizeof r, "%.17g", rating); char d[64]; std::snprintf(d, sizeof d, "%.17g", date);
		std::cout << "],\"price\":" << price << ",\"rating\":" << r << ",\"category\":" << json_string(category) << ",\"date\":" << d << "}\n";
		doc.add_value(0, Xapian::sortable_serialise(double(price)));
		doc.add_value(1, Xapian::sortable_serialise(rating));
		doc.add_value(2, category);
		doc.add_value(3, Xapian::sortable_serialise(date));
		db.add_document(doc);
	}
	db.commit();
	Xapian::Enquire enquire(db);
	auto ids = [&](const Xapian::MSet& mset) {
		std::string out = "["; bool first = true;
		for (auto m = mset.begin(); m != mset.end(); ++m) { out += (first ? "" : ",") + std::to_string(*m); first = false; }
		return out + "]";
	};
	auto text = [&](unsigned q) {
		std::vector<Xapian::Query> terms;
		for (unsigned k = 0; k <= q % 3; ++k) { terms.emplace_back("w" + std::to_string((q * 7 + k * 3) % 50)); }
		return Xapian::Query(q % 2 ? Xapian::Query::OP_AND : Xapian::Query::OP_OR, terms.begin(), terms.end());
	};
	// Ranges over each numeric slot, with Xapian's inclusive bounds.
	for (unsigned q = 0; q < 40; ++q) {
		const unsigned slot = q % 2 ? 1 : 0;
		double lo = slot ? double(random() % 1000) - 500.0 : double(std::int64_t(random() % 2001) - 1000), hi = lo + double(random() % (slot ? 300 : 600));
		enquire.set_query(Xapian::Query(Xapian::Query::OP_VALUE_RANGE, slot, Xapian::sortable_serialise(lo), Xapian::sortable_serialise(hi)));
		enquire.set_sort_by_relevance();
		auto mset = enquire.get_mset(0, db.get_doccount());
		char l[64], h[64]; std::snprintf(l, sizeof l, "%.17g", lo); std::snprintf(h, sizeof h, "%.17g", hi);
		std::cout << "{\"range\":{\"slot\":" << slot << ",\"lo\":" << l << ",\"hi\":" << h << "},\"matches\":" << ids(mset) << "}\n";
	}
	// Sorts: one slot either way, and a multi-key (category ascending, then price descending).
	for (unsigned q = 0; q < 30; ++q) {
		enquire.set_query(text(q));
		const char* mode;
		Xapian::MultiValueKeyMaker keys;
		if (q % 3 == 2) { keys.add_value(2, false); keys.add_value(0, true); enquire.set_sort_by_key(&keys, false); mode = "category asc, price desc"; }
		else { enquire.set_sort_by_value(q % 3 ? 1 : 0, q % 2 == 1); mode = q % 3 ? "rating" : "price"; }
		auto mset = enquire.get_mset(0, 25);
		std::cout << "{\"sort\":" << json_string(mode) << ",\"reverse\":" << (q % 3 != 2 && q % 2 == 1 ? "true" : "false") << ",\"query\":" << json_string(text(q).get_description())
			<< ",\"hits\":" << ids(mset) << "}\n";
	}
	enquire.set_sort_by_relevance();
	// Collapse by category, with counts and both triples, at several check_at_least.
	for (unsigned q = 0; q < 20; ++q) {
		enquire.set_query(text(q));
		enquire.set_collapse_key(2, 1 + q % 3);
		for (Xapian::doccount check : {0u, 50u, db.get_doccount()}) {
			auto mset = enquire.get_mset(0, 10, check);
			std::cout << "{\"collapse\":{\"slot\":2,\"max\":" << 1 + q % 3 << "},\"query\":" << json_string(text(q).get_description()) << ",\"check_at_least\":" << check << ",\"hits\":[";
			bool first = true;
			for (auto m = mset.begin(); m != mset.end(); ++m) { std::cout << (first ? "" : ",") << "[" << *m << "," << m.get_collapse_count() << "]"; first = false; }
			std::cout << "],\"matches\":[" << mset.get_matches_lower_bound() << "," << mset.get_matches_estimated() << "," << mset.get_matches_upper_bound()
				<< "],\"uncollapsed\":[" << mset.get_uncollapsed_matches_lower_bound() << "," << mset.get_uncollapsed_matches_estimated() << "," << mset.get_uncollapsed_matches_upper_bound() << "]}\n";
		}
	}
	enquire.set_collapse_key(Xapian::BAD_VALUENO);
	// MatchSpy over the category, per check_at_least: which documents it saw.
	for (unsigned q = 0; q < 20; ++q) {
		enquire.set_query(text(q));
		for (Xapian::doccount check : {0u, 50u, db.get_doccount()}) {
			Xapian::ValueCountMatchSpy spy(2);
			enquire.clear_matchspies(); enquire.add_matchspy(&spy);
			auto mset = enquire.get_mset(0, 10, check);
			std::cout << "{\"spy\":2,\"query\":" << json_string(text(q).get_description()) << ",\"check_at_least\":" << check << ",\"total\":" << spy.get_total() << ",\"counts\":{";
			bool first = true;
			for (auto v = spy.values_begin(); v != spy.values_end(); ++v) { std::cout << (first ? "" : ",") << json_string(*v) << ":" << v.get_termfreq(); first = false; }
			std::cout << "},\"matches\":[" << mset.get_matches_lower_bound() << "," << mset.get_matches_estimated() << "," << mset.get_matches_upper_bound() << "]}\n";
		}
	}
	enquire.clear_matchspies();
	// Percent with a scored value source beside the text.
	for (unsigned q = 0; q < 20; ++q) {
		Xapian::ValueWeightPostingSource source(1);
		Xapian::Query query(Xapian::Query::OP_AND_MAYBE, text(q), Xapian::Query(&source));
		enquire.set_query(query);
		auto mset = enquire.get_mset(0, 10, db.get_doccount());
		std::cout << "{\"percent\":" << json_string(query.get_description()) << ",\"hits\":[";
		bool first = true;
		for (auto m = mset.begin(); m != mset.end(); ++m) {
			char w[64]; std::snprintf(w, sizeof w, "%.17g", m.get_weight());
			std::cout << (first ? "" : ",") << "[" << *m << "," << w << "," << m.get_percent() << "]"; first = false;
		}
		std::cout << "]}\n";
	}
	return 0;
}

}  // namespace

int main(int argc, char** argv) {
	std::string cmd = argc > 1 ? argv[1] : "";
	if (cmd == "termgen" && argc == 3) { return termgen(argv[2]); }
	if (cmd == "unicode" && argc == 2) { return unicode_table(); }
	if (cmd == "chars" && argc == 2) { return chars(); }
	if (cmd == "infix" && argc == 2) { return infix(); }
	if (cmd == "termgen-xapiand" && argc == 3) { return termgen_xapiand(argv[2]); }
	if (cmd == "parse" && argc == 3) { return parse(argv[2]); }
	if (cmd == "stem" && argc == 4) { return stem(argv[2], argv[3]); }
	if (cmd == "languages" && argc == 2) {
		std::string all = Xapian::Stem::get_available_languages();
		for (std::size_t i = 0, j; i < all.size(); i = j + 1) {
			j = all.find(' ', i);
			if (j == std::string::npos) { j = all.size(); }
			std::cout << all.substr(i, j - i) << '\n';
		}
		return 0;
	}
	if (cmd == "termgen-bench" && argc == 4) { return termgen_bench(argv[2], std::stoul(argv[3])); }
	if (cmd == "rank" && argc == 5) { return rank(argv[2], std::stoul(argv[3]), argv[4]); }
	if (cmd == "values" && argc == 3) { return values(std::stoul(argv[2])); }
	std::cerr << "usage: oracle termgen TEXTS | parse QUERIES | stem LANGUAGE WORDS | rank CORPUS N QUERIES | values N\n";
	return 2;
}
