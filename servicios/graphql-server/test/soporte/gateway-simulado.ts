import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { exportJWK, generateKeyPair, SignJWT, type KeyLike } from 'jose';
import request from 'supertest';
import type { Configuracion } from '../../src/config';

export const EMISOR = 'http://keycloak-ficticio/realms/agro';
export const AUDIENCIA = 'graphql-server';

/** Respuesta simulada de una ruta. Con `nuncaResponde`, la conexión queda abierta hasta detener el servidor. */
export interface Respuesta {
  estado?: number;
  cuerpo?: unknown;
  demoraMs?: number;
  nuncaResponde?: boolean;
}

export interface Llamada {
  ruta: string;
  camino: string;
  headers: http.IncomingHttpHeaders;
}

type Manejador = Respuesta | ((llamada: Llamada, numero: number) => Respuesta);

/**
 * Un servidor HTTP que hace de API Gateway (rutas registradas por cada test) y de Keycloak (JWKS en /certs y
 * token de la cuenta de servicio en /token). Registra cada llamada recibida (spec-consultas.md 2.12).
 */
export class GatewaySimulado {
  readonly llamadas: Llamada[] = [];
  private readonly rutas = new Map<string, Manejador>();
  private servidor!: http.Server;
  private claves!: { privada: KeyLike; jwk: object };
  private claveAjena!: KeyLike;
  base = '';
  tokensEmitidos = 0;
  jwks: Respuesta = {};
  token: Respuesta = {};

  static async iniciar(): Promise<GatewaySimulado> {
    const gateway = new GatewaySimulado();
    const { privateKey, publicKey } = await generateKeyPair('RS256');
    gateway.claves = { privada: privateKey, jwk: { ...(await exportJWK(publicKey)), kid: 'clave-agro', alg: 'RS256' } };
    gateway.claveAjena = (await generateKeyPair('RS256')).privateKey;
    gateway.servidor = http.createServer((req, res) => gateway.atender(req, res));
    await new Promise<void>((listo) => gateway.servidor.listen(0, '127.0.0.1', listo));
    gateway.base = `http://127.0.0.1:${(gateway.servidor.address() as AddressInfo).port}`;
    return gateway;
  }

  configuracion(cambios: Partial<Configuracion> = {}): Configuracion {
    return {
      puerto: 0,
      apiGatewayUrl: this.base,
      keycloakJwksUri: `${this.base}/certs`,
      keycloakIssuer: EMISOR,
      keycloakAudience: AUDIENCIA,
      keycloakTokenUrl: `${this.base}/token`,
      keycloakClientId: 'graphql-server',
      keycloakClientSecret: 'secreto',
      tiempoLimiteLlamadaMs: 4000,
      plazoConsultaMs: 4500,
      maximoLlamadas: 200,
      produccion: false,
      ...cambios,
    };
  }

  registrar(camino: string, manejador: Manejador): void {
    this.rutas.set(camino, manejador);
  }

  llamadasA(camino: string): Llamada[] {
    return this.llamadas.filter((llamada) => llamada.camino === camino);
  }

  reiniciar(): void {
    this.rutas.clear();
    this.llamadas.length = 0;
    this.tokensEmitidos = 0;
    this.jwks = {};
    this.token = {};
  }

  async firmar(
    opciones: { sub?: string; roles?: string[]; aud?: string; iss?: string; vence?: number; ajena?: boolean } = {},
  ): Promise<string> {
    const ahora = Math.floor(Date.now() / 1000);
    return new SignJWT({ realm_access: { roles: opciones.roles ?? ['gerencia'] } })
      .setProtectedHeader({ alg: 'RS256', kid: 'clave-agro' })
      .setSubject(opciones.sub ?? 'usuario-123')
      .setIssuer(opciones.iss ?? EMISOR)
      .setAudience(opciones.aud ?? AUDIENCIA)
      .setIssuedAt(ahora - 60)
      .setExpirationTime(opciones.vence ?? ahora + 300)
      .sign(opciones.ajena ? this.claveAjena : this.claves.privada);
  }

  async detener(): Promise<void> {
    this.servidor.closeAllConnections();
    await new Promise((listo) => this.servidor.close(listo));
  }

  private atender(req: http.IncomingMessage, res: http.ServerResponse): void {
    const url = new URL(req.url ?? '/', this.base);
    if (url.pathname === '/certs') {
      this.responder(res, { cuerpo: { keys: [this.claves.jwk] }, ...this.jwks });
      return;
    }
    if (url.pathname === '/token') {
      this.tokensEmitidos++;
      this.responder(res, { cuerpo: { access_token: `token-servicio-${this.tokensEmitidos}`, expires_in: 300 }, ...this.token });
      return;
    }
    const llamada: Llamada = { ruta: `${url.pathname}${url.search}`, camino: url.pathname, headers: req.headers };
    this.llamadas.push(llamada);
    const manejador = this.rutas.get(url.pathname);
    const numero = this.llamadasA(url.pathname).length;
    const respuesta: Respuesta =
      manejador === undefined
        ? { estado: 404, cuerpo: { codigo: 'RECURSO_NO_ENCONTRADO', mensaje: 'm', detalles: [] } }
        : typeof manejador === 'function'
          ? manejador(llamada, numero)
          : manejador;
    this.responder(res, respuesta);
  }

  private responder(res: http.ServerResponse, respuesta: Respuesta): void {
    if (respuesta.nuncaResponde) {
      return;
    }
    const enviar = () => {
      res.writeHead(respuesta.estado ?? 200, { 'Content-Type': 'application/json' });
      res.end(respuesta.cuerpo === undefined ? '' : JSON.stringify(respuesta.cuerpo));
    };
    if (respuesta.demoraMs) {
      setTimeout(enviar, respuesta.demoraMs);
    } else {
      enviar();
    }
  }
}

/** POST a /api/graphql con el token dado (o sin token si es null). */
export function consultar(app: Parameters<typeof request>[0], token: string | null, query: string, headers: Record<string, string> = {}) {
  const solicitud = request(app).post('/api/graphql').set('Content-Type', 'application/json');
  if (token) {
    solicitud.set('Authorization', `Bearer ${token}`);
  }
  for (const [nombre, valor] of Object.entries(headers)) {
    solicitud.set(nombre, valor);
  }
  return solicitud.send({ query });
}
