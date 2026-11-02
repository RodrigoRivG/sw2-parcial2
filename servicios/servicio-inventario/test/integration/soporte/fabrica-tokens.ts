import { JSONWebKeySet, KeyLike, SignJWT, exportJWK, generateKeyPair } from 'jose';

export const EMISOR_PRUEBA = 'http://keycloak-ficticio/realms/agro';
export const AUDIENCIA_PRUEBA = 'servicio-inventario';

export interface OpcionesToken {
  sub?: string;
  emisor?: string;
  audiencia?: string;
  /** Instante de expiración (segundos desde epoch) o duración como `'5m'`. */
  expira?: number | string;
  firmarConOtraClave?: boolean;
}

/** Firma tokens como los de Keycloak con claves propias; la app de prueba confía en `jwks`. */
export class FabricaTokens {
  private constructor(
    private readonly clavePrivada: KeyLike,
    private readonly claveAjena: KeyLike,
    readonly jwks: JSONWebKeySet,
  ) {}

  static async crear(): Promise<FabricaTokens> {
    const { publicKey, privateKey } = await generateKeyPair('RS256');
    const ajena = await generateKeyPair('RS256');
    const jwk = { ...(await exportJWK(publicKey)), kid: 'prueba', alg: 'RS256', use: 'sig' };
    return new FabricaTokens(privateKey, ajena.privateKey, { keys: [jwk] });
  }

  token(roles: string[], opciones: OpcionesToken = {}): Promise<string> {
    return new SignJWT({ realm_access: { roles } })
      .setProtectedHeader({ alg: 'RS256', kid: 'prueba' })
      .setSubject(opciones.sub ?? `usuario-${roles.join('-') || 'sin-rol'}`)
      .setIssuer(opciones.emisor ?? EMISOR_PRUEBA)
      .setAudience(opciones.audiencia ?? AUDIENCIA_PRUEBA)
      .setIssuedAt()
      .setExpirationTime(opciones.expira ?? '5m')
      .sign(opciones.firmarConOtraClave ? this.claveAjena : this.clavePrivada);
  }

  async bearer(roles: string[], opciones: OpcionesToken = {}): Promise<string> {
    return `Bearer ${await this.token(roles, opciones)}`;
  }
}
