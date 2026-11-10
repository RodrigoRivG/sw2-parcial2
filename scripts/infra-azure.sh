#!/usr/bin/env bash
# Crea o completa la infraestructura base de Azure para el backend. Idempotente:
# volver a ejecutarlo no duplica recursos. PostgreSQL existente se configura
# exclusivamente en .env.despliegue.compartidos; este script no lo modifica.
#
# Uso (Azure Cloud Shell o con Azure CLI instalado):
#   az login
#   bash scripts/infra-azure.sh                    # o REGION=eastus bash scripts/infra-azure.sh
#
# Resultado (privado, permisos 600, ignorado por Git):
#   despliegue/secretos/azure-infra.env    -> agregar al final de AZURE_DEPLOY_ENV
#   despliegue/secretos/azure-github.txt   -> variables del GitHub Environment "azure"
#
# Al terminar la evaluación, borrar TODO con:  az group delete -n sw2-azure --yes
set -euo pipefail

GRUPO=${GRUPO:-sw2-azure}
REGION=${REGION:-brazilsouth}
ENTORNO=${ENTORNO:-sw2-entorno}
RAIZ=$(cd "$(dirname "$0")/.." && pwd)
REPO=${REPO:-$(git -C "$RAIZ" remote get-url origin | sed -E 's#^(git@github\.com:|https://github\.com/)##; s#\.git$##')}
SALIDA="$RAIZ/despliegue/secretos/azure-infra.env"
SALIDA_GITHUB="$RAIZ/despliegue/secretos/azure-github.txt"

paso() { printf '\n== %s\n' "$*"; }
existe() { "$@" --only-show-errors -o none >/dev/null 2>&1; }

az account show -o none 2>/dev/null || { echo 'Ejecutar az login primero.'; exit 1; }
SUSCRIPCION=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
# Sufijo estable por suscripción: ACR y Key Vault requieren nombres únicos globales.
SUFIJO=$(printf '%s' "$SUSCRIPCION$GRUPO" | sha1sum | cut -c1-6)
ACR="sw2acr$SUFIJO"
VAULT="sw2kv$SUFIJO"
echo "Suscripción: $(az account show --query name -o tsv) | región: $REGION | repo: $REPO"

paso 'Regiones permitidas (Azure for Students suele restringirlas)'
PERMITIDAS=$(az policy assignment list --query '[].parameters.listOfAllowedLocations.value | []' -o tsv 2>/dev/null | sort -u || true)
if [ -n "$PERMITIDAS" ] && ! grep -qx "$REGION" <<<"$PERMITIDAS"; then
  echo "La suscripción no permite $REGION. Regiones permitidas:"
  echo "$PERMITIDAS"
  echo 'Repetir con: REGION=<una de ellas> bash scripts/infra-azure.sh'
  exit 1
fi
echo 'Región aceptada.'

paso 'Proveedores y extensión de Container Apps'
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry Microsoft.KeyVault Microsoft.ManagedIdentity; do
  az provider register --namespace "$p" --wait -o none
done
az extension add --name containerapp --upgrade --yes --only-show-errors -o none

paso "Grupo de recursos $GRUPO"
az group create -n "$GRUPO" -l "$REGION" -o none
GRUPO_ID=$(az group show -n "$GRUPO" --query id -o tsv)

paso "Container Registry $ACR (Basic)"
existe az acr show -n "$ACR" -g "$GRUPO" || az acr create -n "$ACR" -g "$GRUPO" -l "$REGION" --sku Basic --admin-enabled false -o none
ACR_ID=$(az acr show -n "$ACR" --query id -o tsv)
ACR_SERVIDOR=$(az acr show -n "$ACR" --query loginServer -o tsv)

paso "Key Vault $VAULT"
if ! existe az keyvault show -n "$VAULT"; then
  # Un vault borrado queda retenido 90 días con el mismo nombre: recuperarlo.
  if [ -n "$(az keyvault list-deleted --query "[?name=='$VAULT'].name" -o tsv 2>/dev/null)" ]; then
    az keyvault recover -n "$VAULT" -o none
  else
    az keyvault create -n "$VAULT" -g "$GRUPO" -l "$REGION" --enable-rbac-authorization true -o none
  fi
fi
VAULT_ID=$(az keyvault show -n "$VAULT" --query id -o tsv)
VAULT_URL=$(az keyvault show -n "$VAULT" --query properties.vaultUri -o tsv)

paso 'Identidades administradas: sw2-apps (contenedores) y sw2-github (despliegue)'
for nombre in sw2-apps sw2-github; do
  existe az identity show -n "$nombre" -g "$GRUPO" || az identity create -n "$nombre" -g "$GRUPO" -l "$REGION" -o none
done
APPS_ID=$(az identity show -n sw2-apps -g "$GRUPO" --query id -o tsv)
APPS_PRINCIPAL=$(az identity show -n sw2-apps -g "$GRUPO" --query principalId -o tsv)
GITHUB_CLIENTE=$(az identity show -n sw2-github -g "$GRUPO" --query clientId -o tsv)
GITHUB_PRINCIPAL=$(az identity show -n sw2-github -g "$GRUPO" --query principalId -o tsv)

paso 'Roles (requiere ser Owner de la suscripción, como en Azure for Students)'
rol() {
  # --assignee-principal-type evita consultar Graph, que los tenants universitarios suelen bloquear.
  az role assignment create --assignee-object-id "$1" --assignee-principal-type ServicePrincipal --role "$2" --scope "$3" --only-show-errors -o none
}
rol "$APPS_PRINCIPAL" AcrPull "$ACR_ID"
rol "$APPS_PRINCIPAL" 'Key Vault Secrets User' "$VAULT_ID"
rol "$GITHUB_PRINCIPAL" Contributor "$GRUPO_ID"
rol "$GITHUB_PRINCIPAL" AcrPush "$ACR_ID"
rol "$GITHUB_PRINCIPAL" 'Key Vault Secrets Officer' "$VAULT_ID"

paso 'Confianza OIDC con GitHub Actions (sin app registration ni secretos)'
existe az identity federated-credential show --name github-azure --identity-name sw2-github -g "$GRUPO" \
  || az identity federated-credential create --name github-azure --identity-name sw2-github -g "$GRUPO" \
       --issuer https://token.actions.githubusercontent.com \
       --subject "repo:$REPO:environment:azure" \
       --audiences api://AzureADTokenExchange -o none

paso "Container Apps Environment $ENTORNO (sin Log Analytics para no pagar ingesta)"
existe az containerapp env show -n "$ENTORNO" -g "$GRUPO" \
  || az containerapp env create -n "$ENTORNO" -g "$GRUPO" -l "$REGION" --environment-mode WorkloadProfiles --logs-destination none -o none
ENTORNO_ID=$(az containerapp env show -n "$ENTORNO" -g "$GRUPO" --query id -o tsv)
DOMINIO=$(az containerapp env show -n "$ENTORNO" -g "$GRUPO" --query properties.defaultDomain -o tsv)

paso 'Archivos de salida'
mkdir -p "$(dirname "$SALIDA")"
umask 077
cat >"$SALIDA" <<EOF
# PRIVADO. Generado por scripts/infra-azure.sh. Agregar al FINAL de AZURE_DEPLOY_ENV
# (las claves repetidas toman el último valor). Las URL de las apps se deducen de
# AZURE_ENVIRONMENT_DOMAIN; no hace falta escribirlas.
AZURE_LOCATION=$REGION
AZURE_ENVIRONMENT_ID=$ENTORNO_ID
AZURE_ENVIRONMENT_DOMAIN=$DOMINIO
AZURE_IDENTITY_ID=$APPS_ID
AZURE_KEYVAULT_URL=${VAULT_URL%/}
EOF
cat >"$SALIDA_GITHUB" <<EOF
Variables del GitHub Environment "azure" (no son secretos):
AZURE_CLIENT_ID=$GITHUB_CLIENTE
AZURE_TENANT_ID=$TENANT
AZURE_SUBSCRIPTION_ID=$SUSCRIPCION
AZURE_RESOURCE_GROUP=$GRUPO
AZURE_REGISTRY_NAME=$ACR
AZURE_REGISTRY_LOGIN_SERVER=$ACR_SERVIDOR
EOF
cat "$SALIDA_GITHUB"
echo
echo "Dominio de las apps: $DOMINIO  (Gateway: https://sw2-api-gateway.$DOMINIO)"
echo "Valores privados en ${SALIDA#"$RAIZ"/} (no se muestran)."
