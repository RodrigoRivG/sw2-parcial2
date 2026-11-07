#!/bin/sh
# Importa credenciales y flujos con IDs fijos (reimportar reemplaza, no duplica),
# publica los flujos y arranca n8n (spec-n8n.md 2.7). Si falta algo, n8n arranca igual.
CRED=/tmp/credenciales.json

if node /opt/agro/preparar.js > "$CRED"; then
  n8n import:credentials --input="$CRED"
  rm -f "$CRED"
  n8n import:workflow --separate --input=/opt/agro/flujos/
  for id in incidenciaRegistrada recordatorioLabores; do
    n8n publish:workflow --id="$id"
  done
else
  rm -f "$CRED"
fi

exec n8n start
