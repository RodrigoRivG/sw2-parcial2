#!/usr/bin/env python3
"""Verifica el realm "agro" de Keycloak contra specs/spec-keycloak-realm.md (CE-KC-01).

Uso (desde la raíz del repositorio, con Keycloak levantado: docker compose --profile auth up -d):

    python3 scripts/verificar-realm.py           # historias 1, 2 y 4 (y las del gateway si está arriba)
    python3 scripts/verificar-realm.py --saga    # además, la prueba de punta a punta de la Saga (CE-KC-02)

Solo usa la biblioteca estándar. Lee secretos y contraseñas del .env; nunca los imprime.
Termina con código 1 si alguna comprobación falla.
"""

import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

KEYCLOAK = "http://localhost:8180"
GATEWAY = "http://localhost:8080"
REALM = "agro"
EMISOR = f"{KEYCLOAK}/realms/{REALM}"
URL_TOKEN = f"{EMISOR}/protocol/openid-connect/token"

SERVICIOS = {"servicio-gestion", "servicio-inventario", "servicio-operaciones", "servicio-ia"}
ROLES_DEL_SISTEMA = {
    "administrador", "gerencia", "tecnico_campo",
    "lectura_gestion", "estado_campania", "lectura_inventario", "lectura_operaciones",
}

# RQ-KC-06
USUARIOS = {
    "admin.prueba": {"administrador"},
    "tecnico.prueba": {"tecnico_campo"},
    "gerencia.prueba": {"gerencia"},
    "multirol.prueba": {"administrador", "gerencia"},
}

# RQ-KC-04: client -> (variable del secreto, roles, audiencias)
CUENTAS_DE_SERVICIO = {
    "servicio-operaciones": ("OPERACIONES_CLIENT_SECRET", {"estado_campania"}, {"servicio-gestion"}),
    "servicio-ia": ("IA_CLIENT_SECRET", {"lectura_gestion", "lectura_inventario", "lectura_operaciones"},
                    {"servicio-gestion", "servicio-inventario", "servicio-operaciones"}),
    "graphql-server": ("GRAPHQL_CLIENT_SECRET",
                       {"lectura_gestion", "estado_campania", "lectura_inventario", "lectura_operaciones"}, SERVICIOS),
    "n8n": ("N8N_CLIENT_SECRET", {"lectura_inventario", "lectura_operaciones"},
            {"servicio-inventario", "servicio-operaciones", "servicio-ia"}),
}

resultados = {"ok": 0, "falla": 0, "omitida": 0}


# ---------------------------------------------------------------- utilidades

def leer_env():
    ruta = Path(__file__).resolve().parent.parent / ".env"
    valores = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip()
    return valores


def comprobar(descripcion, condicion, detalle=""):
    if condicion:
        resultados["ok"] += 1
        print(f"  OK      {descripcion}")
    else:
        resultados["falla"] += 1
        print(f"  FALLA   {descripcion}" + (f" — {detalle}" if detalle else ""))
    return condicion


def omitir(descripcion, motivo):
    resultados["omitida"] += 1
    print(f"  OMITIDA {descripcion} — {motivo}")


def http(metodo, url, token=None, cuerpo=None, formulario=None, headers=None):
    """Devuelve (estado, headers, cuerpo JSON o texto). Nunca lanza por un código HTTP de error."""
    datos = None
    cabeceras = dict(headers or {})
    if formulario is not None:
        datos = urllib.parse.urlencode(formulario).encode()
        cabeceras["Content-Type"] = "application/x-www-form-urlencoded"
    elif cuerpo is not None:
        datos = json.dumps(cuerpo).encode()
        cabeceras["Content-Type"] = "application/json"
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    solicitud = urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras)
    try:
        with urllib.request.urlopen(solicitud, timeout=20) as respuesta:
            return respuesta.status, dict(respuesta.headers), _decodificar(respuesta.read())
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), _decodificar(error.read())


def _decodificar(contenido):
    try:
        return json.loads(contenido) if contenido else None
    except ValueError:
        return contenido.decode(errors="replace")


def reclamos(token):
    carga = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))


def audiencias(claims):
    aud = claims.get("aud", [])
    return set([aud] if isinstance(aud, str) else aud)


def token_usuario(usuario, clave):
    estado, _, cuerpo = http("POST", URL_TOKEN, formulario={
        "grant_type": "password", "client_id": "agro-pruebas", "username": usuario, "password": clave,
        "scope": "openid"})
    return cuerpo["access_token"] if estado == 200 else None


def token_servicio(client_id, secreto):
    estado, _, cuerpo = http("POST", URL_TOKEN, formulario={
        "grant_type": "client_credentials", "client_id": client_id, "client_secret": secreto})
    return (cuerpo["access_token"] if estado == 200 else None), estado


def codigo(cuerpo):
    return cuerpo.get("codigo") if isinstance(cuerpo, dict) else None


# ---------------------------------------------------------------- historias

def historia_1(clave):
    print("\nHistoria 1 — Iniciar sesión con un rol")
    tokens = {}
    for usuario, roles in USUARIOS.items():
        token = token_usuario(usuario, clave)
        if not comprobar(f"{usuario}: obtiene un token", token is not None):
            continue
        tokens[usuario] = token
        c = reclamos(token)
        roles_token = set(c.get("realm_access", {}).get("roles", [])) & ROLES_DEL_SISTEMA
        comprobar(f"{usuario}: iss es {EMISOR}", c.get("iss") == EMISOR, c.get("iss"))
        comprobar(f"{usuario}: roles {sorted(roles)}", roles_token == roles, sorted(roles_token))
        comprobar(f"{usuario}: aud con los cuatro servicios", SERVICIOS <= audiencias(c), sorted(audiencias(c)))
        comprobar(f"{usuario}: trae name y preferred_username",
                  bool(c.get("name")) and c.get("preferred_username") == usuario)
    estado, _, _ = http("POST", URL_TOKEN, formulario={
        "grant_type": "password", "client_id": "agro-pruebas", "username": "admin.prueba",
        "password": clave + "-incorrecta"})
    comprobar("contraseña incorrecta: Keycloak no emite token (401)", estado == 401, estado)
    return tokens


def historia_2(env):
    print("\nHistoria 2 — Cuentas de servicio con permisos mínimos")
    tokens = {}
    for client_id, (variable, roles, auds) in CUENTAS_DE_SERVICIO.items():
        secreto = env.get(variable, "")
        if not comprobar(f"{client_id}: {variable} tiene valor en .env", bool(secreto)):
            continue
        token, estado = token_servicio(client_id, secreto)
        if not comprobar(f"{client_id}: obtiene un token con client credentials", token is not None, estado):
            continue
        tokens[client_id] = token
        c = reclamos(token)
        roles_token = set(c.get("realm_access", {}).get("roles", [])) & ROLES_DEL_SISTEMA
        comprobar(f"{client_id}: roles exactos {sorted(roles)}", roles_token == roles, sorted(roles_token))
        comprobar(f"{client_id}: aud exacta {sorted(auds)}", audiencias(c) & SERVICIOS == auds,
                  sorted(audiencias(c)))
        _, estado_malo = token_servicio(client_id, secreto + "-incorrecto")
        comprobar(f"{client_id}: secreto incorrecto rechazado (401)", estado_malo == 401, estado_malo)
        _, estado_vacio = token_servicio(client_id, "")
        comprobar(f"{client_id}: secreto vacío rechazado", estado_vacio != 200, estado_vacio)
    return tokens


def historia_4(tokens_usuario, tokens_servicio):
    print("\nHistoria 4 — Gestionar usuarios con la API de administración (RF-32)")
    url = f"{KEYCLOAK}/admin/realms/{REALM}/users?max=5"
    esperados = {"admin.prueba": 200, "tecnico.prueba": 403, "gerencia.prueba": 403}
    for usuario, esperado in esperados.items():
        if usuario in tokens_usuario:
            estado, _, _ = http("GET", url, token=tokens_usuario[usuario])
            comprobar(f"{usuario}: GET /admin/realms/agro/users responde {esperado}", estado == esperado, estado)
    if "servicio-operaciones" in tokens_servicio:
        estado, _, _ = http("GET", url, token=tokens_servicio["servicio-operaciones"])
        comprobar("cuenta de servicio: GET /admin/realms/agro/users responde 403", estado == 403, estado)


def gateway_arriba():
    try:
        estado, _, _ = http("GET", f"{GATEWAY}/salud")
        return estado == 200
    except (urllib.error.URLError, OSError):
        return False


def a_traves_del_gateway(tokens_usuario, tokens_servicio):
    print("\nHistorias 1.4 y 2.1–2.2 — Tokens contra los servicios a través del gateway")
    if not gateway_arriba():
        omitir("comprobaciones con el gateway", f"{GATEWAY}/salud no responde")
        return

    casos = [
        # (descripción, token, método, ruta, estado esperado, código esperado o None)
        ("admin.prueba lee parcelas", tokens_usuario.get("admin.prueba"), "/api/gestion/v1/parcelas", 200, None),
        ("tecnico.prueba no lee movimientos de inventario", tokens_usuario.get("tecnico.prueba"),
         "/api/inventario/v1/movimientos", 403, "SIN_PERMISO"),
        ("gerencia.prueba lee labores confirmadas", tokens_usuario.get("gerencia.prueba"),
         "/api/operaciones/v1/labores?estado=CONFIRMADA", 200, None),
        ("servicio-operaciones consulta el estado de una campaña inexistente",
         tokens_servicio.get("servicio-operaciones"), f"/api/gestion/v1/campanias/{uuid.uuid4()}/estado", 404,
         "CAMPANIA_NO_ENCONTRADA"),
        ("servicio-operaciones no lee parcelas (sin lectura_gestion)", tokens_servicio.get("servicio-operaciones"),
         "/api/gestion/v1/parcelas", 403, "SIN_PERMISO"),
        ("servicio-operaciones no llega a inventario (fuera de su aud)", tokens_servicio.get("servicio-operaciones"),
         "/api/inventario/v1/insumos", 401, "NO_AUTENTICADO"),
        ("n8n lee el estado del inventario", tokens_servicio.get("n8n"), "/api/inventario/v1/estado-inventario", 200,
         None),
        ("n8n no llega a gestión (fuera de su aud)", tokens_servicio.get("n8n"), "/api/gestion/v1/parcelas", 401,
         "NO_AUTENTICADO"),
    ]
    for descripcion, token, ruta, esperado, codigo_esperado in casos:
        if token is None:
            omitir(descripcion, "no hay token")
            continue
        estado, _, cuerpo = http("GET", GATEWAY + ruta, token=token)
        if estado == 503 and codigo(cuerpo) == "SERVICIO_NO_DISPONIBLE":
            omitir(descripcion, f"el servicio de {ruta.split('/')[2]} no está levantado")
            continue
        comprobar(f"{descripcion}: {esperado}" + (f" {codigo_esperado}" if codigo_esperado else ""),
                  estado == esperado and (codigo_esperado is None or codigo(cuerpo) == codigo_esperado),
                  f"{estado} {codigo(cuerpo)}")


# ---------------------------------------------------------------- Saga de punta a punta (CE-KC-02)

def saga_punta_a_punta(tokens_usuario):
    print("\nSaga de punta a punta — labor con insumos a través del gateway (CE-KC-02, CE-SAG-05)")
    admin, tecnico = tokens_usuario.get("admin.prueba"), tokens_usuario.get("tecnico.prueba")
    if not (admin and tecnico and gateway_arriba()):
        omitir("Saga de punta a punta", "faltan tokens o el gateway no responde")
        return
    sufijo = uuid.uuid4().hex[:8]
    hoy = time.strftime("%Y-%m-%d", time.gmtime())

    def crear(ruta, cuerpo, token=admin, esperado=201):
        estado, _, respuesta = http("POST", GATEWAY + ruta, token=token, cuerpo=cuerpo)
        if not comprobar(f"POST {ruta}: {esperado}", estado == esperado, f"{estado} {respuesta}"):
            raise RuntimeError(ruta)
        return respuesta

    try:
        parcela = crear("/api/gestion/v1/parcelas",
                        {"nombre": f"Lote E2E {sufijo}", "superficieHectareas": "10.0000", "ubicacion": "Prueba"})
        cultivo = crear("/api/gestion/v1/cultivos",
                        {"nombre": f"Soya E2E {sufijo}", "variedad": "Munasqa", "unidadMedida": "KILOGRAMO"})
        campania = crear("/api/gestion/v1/campanias", {
            "nombre": f"Campaña E2E {sufijo}", "idParcela": parcela["id"], "idCultivo": cultivo["id"],
            "fechaInicio": hoy, "fechaFin": time.strftime("%Y-%m-%d", time.gmtime(time.time() + 120 * 86400))})
        estado, _, respuesta = http("PUT", f"{GATEWAY}/api/gestion/v1/campanias/{campania['id']}/estado", token=admin,
                                    cuerpo={"estadoDestino": "EN_CURSO", "version": campania["version"]})
        if not comprobar("la campaña pasa a EN_CURSO", estado == 200, f"{estado} {respuesta}"):
            return
        insumo = crear("/api/inventario/v1/insumos", {
            "nombre": f"Urea E2E {sufijo}", "categoria": "FERTILIZANTE", "unidad": "KILOGRAMO",
            "nivelMinimo": "10", "costoUnitario": "4.85", "stockInicial": "100"})
    except RuntimeError:
        return

    def registrar_labor(cantidad):
        id_labor = str(uuid.uuid4())
        id_correlacion = f"e2e-{sufijo}-{cantidad}"
        estado, _, respuesta = http("POST", f"{GATEWAY}/api/operaciones/v1/labores", token=tecnico,
                                    headers={"X-Correlation-Id": id_correlacion}, cuerpo={
            "idOperacion": id_labor, "fechaCreacion": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tipoLabor": "FERTILIZACION", "idParcela": parcela["id"], "idCampania": campania["id"],
            "fechaEjecucion": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "insumos": [{"idInsumo": insumo["id"], "cantidad": cantidad}]})
        comprobar(f"labor con {cantidad} kg registrada por tecnico.prueba: 201 PENDIENTE",
                  estado == 201 and respuesta.get("estado") == "PENDIENTE", f"{estado} {respuesta}")
        if isinstance(respuesta, dict) and respuesta.get("validacionCampania") == "PENDIENTE":
            print("          (validación de campaña diferida: operaciones no pudo consultar a gestión)")
        final = None
        for _ in range(30):
            _, _, labor = http("GET", f"{GATEWAY}/api/operaciones/v1/labores/{id_labor}", token=tecnico)
            if isinstance(labor, dict) and labor.get("estado") not in (None, "PENDIENTE"):
                final = labor
                break
            time.sleep(1)
        return final, id_correlacion

    labor, id_correlacion = registrar_labor("20")
    comprobar("con stock suficiente la labor queda CONFIRMADA",
              labor is not None and labor["estado"] == "CONFIRMADA", labor and labor.get("estado"))
    _, _, insumo_actual = http("GET", f"{GATEWAY}/api/inventario/v1/insumos/{insumo['id']}", token=admin)
    comprobar("el stock bajó de 100 a 80 kg", insumo_actual.get("stock") == "80.000", insumo_actual.get("stock"))
    _, _, costos = http("GET", f"{GATEWAY}/api/gestion/v1/campanias/{campania['id']}/costos", token=admin)
    montos = [c.get("monto") for c in (costos or {}).get("items", []) if c.get("origen") == "SAGA"]
    comprobar("gestión registró el costo de la Saga (20 × 4.85 = 97.00)", "97.00" in montos, montos)
    comprobar_logs(id_correlacion)

    labor, _ = registrar_labor("500")
    comprobar("con stock insuficiente la labor queda RECHAZADA",
              labor is not None and labor["estado"] == "RECHAZADA", labor and labor.get("estado"))
    _, _, insumo_actual = http("GET", f"{GATEWAY}/api/inventario/v1/insumos/{insumo['id']}", token=admin)
    comprobar("el stock sigue en 80 kg", insumo_actual.get("stock") == "80.000", insumo_actual.get("stock"))


def comprobar_logs(id_correlacion):
    """El mismo X-Correlation-Id aparece en el gateway y en servicio-operaciones (RNF-22)."""
    for servicio in ("api-gateway", "servicio-operaciones"):
        salida = subprocess.run(["docker", "compose", "logs", "--no-log-prefix", servicio],
                                capture_output=True, text=True, check=False).stdout
        comprobar(f"el idCorrelacion {id_correlacion} aparece en los logs de {servicio}", id_correlacion in salida)


# ---------------------------------------------------------------- principal

def main():
    env = leer_env()
    clave = env.get("KEYCLOAK_CLAVE_USUARIOS_PRUEBA", "")
    if not clave:
        print("Falta KEYCLOAK_CLAVE_USUARIOS_PRUEBA en .env (ver .env.example).")
        return 1
    try:
        http("GET", f"{EMISOR}/.well-known/openid-configuration")
    except (urllib.error.URLError, OSError):
        print(f"Keycloak no responde en {KEYCLOAK}. Levántalo con: docker compose --profile auth up -d keycloak")
        return 1

    tokens_usuario = historia_1(clave)
    tokens_servicio = historia_2(env)
    historia_4(tokens_usuario, tokens_servicio)
    a_traves_del_gateway(tokens_usuario, tokens_servicio)
    if "--saga" in sys.argv:
        saga_punta_a_punta(tokens_usuario)

    print(f"\n{resultados['ok']} correctas, {resultados['falla']} fallidas, {resultados['omitida']} omitidas")
    return 1 if resultados["falla"] else 0


if __name__ == "__main__":
    sys.exit(main())
