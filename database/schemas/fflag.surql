DEFINE TABLE fflag SCHEMAFULL;

DEFINE FIELD type ON fflag TYPE number DEFAULT 0;
DEFINE FIELD value ON fflag TYPE any DEFAULT "";

DEFINE FIELD created ON fflag TYPE datetime DEFAULT time::now() READONLY;
DEFINE FIELD updated ON fflag TYPE datetime VALUE time::now() DEFAULT time::now();

DEFINE INDEX fflagNameIndex ON TABLE fflag COLUMNS id SEARCH ANALYZER ascii BM25 HIGHLIGHTS;