DEFINE TABLE login_token SCHEMALESS;

DEFINE FIELD type ON login_token TYPE string;
DEFINE FIELD created ON login_token TYPE datetime DEFAULT time::now();