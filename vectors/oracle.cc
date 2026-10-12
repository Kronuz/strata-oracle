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
#include <xapian.h>

#include <cstdio>
#include <fstream>
#include <iostream>
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
	if (cmd == "rank" && argc == 5) { return rank(argv[2], std::stoul(argv[3]), argv[4]); }
	std::cerr << "usage: oracle termgen TEXTS | parse QUERIES | stem LANGUAGE WORDS | rank CORPUS N QUERIES\n";
	return 2;
}
