DEFINE TABLE bot_data SCHEMAFULL;

DEFINE FIELD value ON bot_data TYPE any;

DEFINE INDEX botDataIndex ON bot_data COLUMNS key UNIQUE;