// Records Xapian's observable behavior as JSON-lines test vectors for strata's
// clean-room compatibility work. GPL (links Xapian); never shipped with strata.
//
//   oracle termgen  TEXTS_FILE             one text per line -> terms, wdf, positions per stem strategy
//   oracle termgen-xapiand TEXTS_FILE      prefixes, wdf increments, stoppers, positionless indexing
//   oracle parse    QUERIES_FILE           one query per line -> descriptions per flag set
//   oracle stem     LANGUAGE WORDS_FILE    one word per line -> stem
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
	};
	const config configs[] = {
		{"prefix", "XA", 1, true, Xapian::TermGenerator::STOP_NONE, Xapian::TermGenerator::STEM_NONE},
		{"wdf_inc_3", "", 3, true, Xapian::TermGenerator::STOP_NONE, Xapian::TermGenerator::STEM_NONE},
		{"positionless", "XB", 2, false, Xapian::TermGenerator::STOP_NONE, Xapian::TermGenerator::STEM_SOME},
		{"stop_all", "", 1, true, Xapian::TermGenerator::STOP_ALL, Xapian::TermGenerator::STEM_SOME},
		{"stop_stemmed", "", 1, true, Xapian::TermGenerator::STOP_STEMMED, Xapian::TermGenerator::STEM_SOME},
		{"stop_none_stopper", "", 1, true, Xapian::TermGenerator::STOP_NONE, Xapian::TermGenerator::STEM_SOME},
	};
	for (const auto& text : lines(path)) {
		for (const auto& c : configs) {
			Xapian::TermGenerator g;
			g.set_stemmer(Xapian::Stem("english"));
			g.set_stemming_strategy(c.stem);
			g.set_stopper(&stopper);
			g.set_stopper_strategy(c.stop);
			Xapian::Document doc;
			g.set_document(doc);
			if (c.positions) {
				g.index_text(text, c.wdf_inc, c.prefix);
			} else {
				g.index_text_without_positions(text, c.wdf_inc, c.prefix);
			}
			std::cout << "{\"text\":" << json_string(text) << ",\"config\":\"" << c.name << "\",\"prefix\":" << json_string(c.prefix)
			          << ",\"wdf_inc\":" << c.wdf_inc << ",\"positions\":" << (c.positions ? "true" : "false") << ",\"terms\":" << terms_json(doc) << "}\n";
		}
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
				          << ",\"terms\":" << terms_json(doc) << "}\n";
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
	if (cmd == "termgen-xapiand" && argc == 3) { return termgen_xapiand(argv[2]); }
	if (cmd == "parse" && argc == 3) { return parse(argv[2]); }
	if (cmd == "stem" && argc == 4) { return stem(argv[2], argv[3]); }
	if (cmd == "rank" && argc == 5) { return rank(argv[2], std::stoul(argv[3]), argv[4]); }
	std::cerr << "usage: oracle termgen TEXTS | parse QUERIES | stem LANGUAGE WORDS | rank CORPUS N QUERIES\n";
	return 2;
}
