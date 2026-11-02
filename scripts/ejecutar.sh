#!/usr/bin/env bash
# Ejecuta un comando dentro de la imagen de desarrollo de un servicio, sin
# instalar Java, Node, PHP ni Python en la máquina. Sirve para tests
# (incluido Testcontainers), generadores y herramientas de cada stack.
#
# Uso:
#   ./scripts/ejecutar.sh <servicio> <comando...>
#
# Ejemplos:
#   ./scripts/ejecutar.sh servicio-gestion mvn -B verify
#   ./scripts/ejecutar.sh servicio-inventario npm test
#   ./scripts/ejecutar.sh servicio-operaciones ./vendor/bin/pest
#   ./scripts/ejecutar.sh servicio-ia pytest
#   ./scripts/ejecutar.sh servicio-ia ruff check .
#
# El servicio no necesita estar levantado. La infraestructura base sí
# (docker compose up -d) si los tests usan la red de Compose.
set -euo pipefail

SERVICIO="${1:?Uso: $0 <servicio> <comando...>}"
shift
[ "$#" -gt 0 ] || { echo "Falta el comando a ejecutar" >&2; exit 1; }

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SOCK=/var/run/docker.sock
EXTRA=()

case "$SERVICIO" in
  servicio-gestion|api-gateway)
    IMAGEN=sw2/spring-dev
    EXTRA+=(-v sw2_maven-cache:/cache) ;;
  servicio-inventario|graphql-server)
    IMAGEN=sw2/node-dev ;;
  servicio-operaciones)
    IMAGEN=sw2/laravel-dev ;;
  servicio-ia)
    IMAGEN=sw2/python-dev
    EXTRA+=(-v sw2_ia-venv:/venv -v sw2_ia-cache:/cache) ;;
  *)
    echo "Servicio desconocido: $SERVICIO" >&2
    exit 1 ;;
esac

if [ ! -d "$RAIZ/servicios/$SERVICIO" ]; then
  echo "No existe servicios/$SERVICIO" >&2
  exit 1
fi

# Construye la imagen si todavía no existe
if ! docker image inspect "$IMAGEN" >/dev/null 2>&1; then
  (cd "$RAIZ" && docker compose --profile todo build "$SERVICIO")
fi

# Se une a la red de Compose si existe (para llegar a dynamodb, rabbitmq, etc.)
if docker network inspect sw2_default >/dev/null 2>&1; then
  EXTRA+=(--network sw2_default)
fi

# Terminal interactiva solo si existe (los agentes suelen ejecutar sin TTY)
[ -t 0 ] && [ -t 1 ] && EXTRA+=(-it)
[ -f "$RAIZ/.env" ] && EXTRA+=(--env-file "$RAIZ/.env")

# Testcontainers necesita el socket de Docker y el grupo que lo puede usar
docker run --rm \
  -v "$RAIZ/servicios/$SERVICIO":/app \
  -w /app \
  -v "$SOCK":/var/run/docker.sock \
  --group-add "$(stat -L -c %g "$SOCK")" \
  --add-host host.docker.internal:host-gateway \
  -e TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal \
  "${EXTRA[@]}" \
  "$IMAGEN" "$@"
