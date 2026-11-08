import { Decimal, Fecha, FechaHora, FechaOFechaHora } from '../../src/esquema/escalares';
import { aplicarPermisos, exigirRol } from '../../src/seguridad/permisos';
import { leerConfiguracion } from '../../src/config';

describe('escalares', () => {
  it('devuelven el texto del servicio sin cambios y rechazan números y formatos inválidos', () => {
    expect(Decimal.serialize('820.50')).toBe('820.50');
    expect(Fecha.serialize('2026-11-15')).toBe('2026-11-15');
    expect(FechaHora.serialize('2026-11-16T12:00:00.123456Z')).toBe('2026-11-16T12:00:00.123456Z');
    expect(() => Decimal.serialize(820.5)).toThrow();
    expect(() => Decimal.parseValue('1e3')).toThrow();
    expect(() => Fecha.parseValue('15/11/2026')).toThrow();
    expect(() => FechaHora.serialize('2026-11-16')).toThrow();
    expect(FechaOFechaHora.serialize('2026-11-16')).toBe('2026-11-16');
    expect(FechaOFechaHora.serialize('2026-11-16T12:00:00Z')).toBe('2026-11-16T12:00:00Z');
    expect(() => FechaOFechaHora.serialize('2026-11-16 12:00')).toThrow();
  });
});

describe('permisos', () => {
  it('exigirRol deja pasar a quien tiene uno de los roles y rechaza al resto con SIN_PERMISO', () => {
    expect(() => exigirRol({ sub: 'u', roles: ['gerencia'] }, ['gerencia'])).not.toThrow();
    expect(() => exigirRol({ sub: 'u', roles: ['administrador'] }, ['gerencia'])).toThrow(
      expect.objectContaining({ codigo: 'SIN_PERMISO' }),
    );
  });

  it('aplicarPermisos falla si a la tabla le falta su resolver', () => {
    expect(() => aplicarPermisos({ Query: {} })).toThrow(/Falta el resolver/);
  });
});

describe('configuración', () => {
  const entorno = {
    API_GATEWAY_URL: 'http://gw/',
    KEYCLOAK_JWKS_URI: 'j',
    KEYCLOAK_ISSUER: 'i',
    KEYCLOAK_AUDIENCE: 'graphql-server',
    KEYCLOAK_TOKEN_URL: 't',
    KEYCLOAK_CLIENT_ID: 'graphql-server',
    KEYCLOAK_CLIENT_SECRET: 's',
  };

  it('aplica los valores por defecto y rechaza un plazo que no cumple RNF-05 o una variable faltante', () => {
    const configuracion = leerConfiguracion(entorno);
    expect(configuracion).toMatchObject({ apiGatewayUrl: 'http://gw', plazoConsultaMs: 4500, maximoLlamadas: 200, puerto: 4000 });
    expect(() => leerConfiguracion({ ...entorno, GRAPHQL_PLAZO_CONSULTA_MS: '5000' })).toThrow(/RNF-05/);
    expect(() => leerConfiguracion({ ...entorno, GRAPHQL_MAXIMO_LLAMADAS: 'x' })).toThrow();
    expect(() => leerConfiguracion({ ...entorno, KEYCLOAK_AUDIENCE: '' })).toThrow(/KEYCLOAK_AUDIENCE/);
  });
});
