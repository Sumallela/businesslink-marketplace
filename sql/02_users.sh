#!/bin/bash
# Creates the two day-to-day accounts with least privilege. Runs once, on the database's first start.
#   etl_user    : read + write rows in the project database (no CREATE/DROP/ALTER)
#   viewer_user : SELECT only (used by the Streamlit app and the MCP server)
# Passwords come from .env (ETL_PASSWORD / VIEWER_PASSWORD); they are never written to this file.
# (Use passwords without single quotes or backslashes.)
set -euo pipefail

mysql --protocol=socket -uroot -p"${MYSQL_ROOT_PASSWORD}" <<EOSQL
CREATE USER '${ETL_USER}'@'%' IDENTIFIED BY '${ETL_PASSWORD}';
CREATE USER '${VIEWER_USER}'@'%' IDENTIFIED BY '${VIEWER_PASSWORD}';
GRANT SELECT, INSERT, UPDATE, DELETE ON \`${MYSQL_DATABASE}\`.* TO '${ETL_USER}'@'%';
GRANT SELECT ON \`${MYSQL_DATABASE}\`.* TO '${VIEWER_USER}'@'%';
FLUSH PRIVILEGES;
EOSQL
