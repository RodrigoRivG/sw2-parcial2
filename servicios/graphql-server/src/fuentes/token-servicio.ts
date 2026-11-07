import { TIEMPO_LIMITE_TOKEN_SERVICIO_MS, type Configuracion } from '../config';

/** La cuenta de servicio no pudo obtener su token. */
export class TokenNoDisponible extends Error {}

interface TokenEnCache {
  valor: string;
  venceEn: number;
}

const MARGEN_RENOVACION_MS = 30_000;

/**
 * Token de la cuenta `graphql-server` (client credentials), compartido entre consultas (2.6). La obtención tiene
 * su propio tiempo límite y nunca recibe la señal del plazo de una consulta: cada consulta espera la misma
 * obtención compitiendo contra su propio plazo.
 */
export class TokenServicio {
  private token?: TokenEnCache;
  private enCurso?: Promise<string>;

  constructor(private readonly configuracion: Configuracion) {}

  async obtener(senalPlazo: AbortSignal): Promise<string> {
    if (this.token && Date.now() < this.token.venceEn - MARGEN_RENOVACION_MS) {
      return this.token.valor;
    }
    this.enCurso ??= this.pedir().finally(() => {
      this.enCurso = undefined;
    });
    return esperar(this.enCurso, senalPlazo);
  }

  invalidar(): void {
    this.token = undefined;
  }

  private async pedir(): Promise<string> {
    let respuesta: Response;
    try {
      respuesta = await fetch(this.configuracion.keycloakTokenUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'client_credentials',
          client_id: this.configuracion.keycloakClientId,
          client_secret: this.configuracion.keycloakClientSecret,
        }),
        signal: AbortSignal.timeout(TIEMPO_LIMITE_TOKEN_SERVICIO_MS),
      });
      if (!respuesta.ok) {
        throw new TokenNoDisponible(`Keycloak respondió ${respuesta.status}`);
      }
      const cuerpo = (await respuesta.json()) as { access_token: string; expires_in: number };
      this.token = { valor: cuerpo.access_token, venceEn: Date.now() + cuerpo.expires_in * 1000 };
      return cuerpo.access_token;
    } catch (error) {
      throw error instanceof TokenNoDisponible ? error : new TokenNoDisponible(String(error));
    }
  }
}

/** Espera la promesa compartida, pero deja de esperar si la señal de esta consulta se dispara antes. */
function esperar<T>(promesa: Promise<T>, senal: AbortSignal): Promise<T> {
  if (senal.aborted) {
    return Promise.reject(senal.reason);
  }
  return new Promise<T>((resolver, rechazar) => {
    const alAbortar = () => rechazar(senal.reason);
    senal.addEventListener('abort', alAbortar, { once: true });
    promesa.then(
      (valor) => {
        senal.removeEventListener('abort', alAbortar);
        resolver(valor);
      },
      (error) => {
        senal.removeEventListener('abort', alAbortar);
        rechazar(error);
      },
    );
  });
}
