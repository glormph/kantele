psql -U postgres << EOF
CREATE ROLE ${KANTELE_ROLE} WITH LOGIN PASSWORD '${KANTELE_PASSWORD}';
ALTER USER ${KANTELE_ROLE} CREATEDB;
CREATE DATABASE ${KANTELE_DB};
EOF
