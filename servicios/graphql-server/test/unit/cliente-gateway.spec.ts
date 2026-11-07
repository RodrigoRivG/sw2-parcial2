import { ClienteGateway, type ContextoLlamada } from '../../src/fuentes/cliente-gateway';
import { TokenServicio } from '../../src/fuentes/token-servicio';
import { PlazoConsultaVencido } from '../../src/web/errores';
import { GatewaySimulado, type Respuesta } from '../soporte/gateway-simulado';

let gateway: GatewaySimulado;

beforeAll(async () => {
  gateway = await GatewaySimulado.iniciar();
});
afterAll(() => gateway.detener());
beforeEach(() => gateway.reiniciar());

function contexto(senalPlazo = new AbortController().signal): ContextoLlamada {
  return { idCorrelacion: 'abc-123', senalPlazo, estadisticas: { operacion: 'x', llamadas: 0, errores: 0 } };
}

function cliente(cambios = {}) {
  const configuracion = gateway.configuracion(cambios);
  return new ClienteGateway(configuracion, new TokenServicio(configuracion));
}

describe('ClienteGateway', () => {
  it.each<[string, Respuesta, string | null]>([
    ['400 con los detalles del servicio', { estado: 400, cuerpo: { detalles: ['tamanio'] } }, 'DATOS_INVALIDOS'],
    ['403 (permiso faltante en el realm)', { estado: 403 }, 'ERROR_INTERNO'],
    ['503 del gateway', { estado: 503 }, 'DEPENDENCIA_NO_DISPONIBLE'],
    ['504 del gateway', { estado: 504 }, 'DEPENDENCIA_NO_DISPONIBLE'],
    ['500 inesperado', { estado: 500 }, 'ERROR_INTERNO'],
    ['tiempo límite de la llamada', { nuncaResponde: true }, 'DEPENDENCIA_NO_DISPONIBLE'],
  ])('traduce %s', async (_caso, respuesta, codigo) => {
    gateway.registrar('/api/gestion/v1/x', respuesta);
    const promesa = cliente({ tiempoLimiteLlamadaMs: 200 }).get(contexto(), '/api/gestion/v1/x');
    await expect(promesa).rejects.toMatchObject({ codigo });
    if (codigo === 'DATOS_INVALIDOS') {
      await expect(promesa).rejects.toMatchObject({ detalles: ['tamanio'] });
    }
  });

  it('con porId, un 404 devuelve null; propaga la correlación y el token de servicio', async () => {
    expect(await cliente().get(contexto(), '/api/gestion/v1/parcelas/p9', {}, true)).toBeNull();
    expect(gateway.llamadas[0].headers).toMatchObject({
      'x-correlation-id': 'abc-123',
      authorization: 'Bearer token-servicio-1',
    });
  });

  it('ante un 401 renueva el token y repite una sola vez', async () => {
    gateway.registrar('/api/gestion/v1/x', (_l, numero) => (numero === 1 ? { estado: 401 } : { cuerpo: { ok: true } }));
    const ctx = contexto();
    expect(await cliente().get(ctx, '/api/gestion/v1/x')).toEqual({ ok: true });
    expect(gateway.llamadasA('/api/gestion/v1/x')[1].headers.authorization).toBe('Bearer token-servicio-2');
    expect(ctx.estadisticas.llamadas).toBe(2);

    gateway.registrar('/api/gestion/v1/y', { estado: 401 });
    await expect(cliente().get(contexto(), '/api/gestion/v1/y')).rejects.toMatchObject({ codigo: 'DEPENDENCIA_NO_DISPONIBLE' });
  });

  it('corta por plazo (también esperando la respuesta) sin descontar presupuesto cuando ya venció', async () => {
    gateway.registrar('/api/gestion/v1/x', { nuncaResponde: true });
    const plazo = new AbortController();
    const ctx = contexto(plazo.signal);
    const promesa = cliente().get(ctx, '/api/gestion/v1/x');
    setTimeout(() => plazo.abort(new PlazoConsultaVencido()), 100);
    await expect(promesa).rejects.toMatchObject({ codigo: 'DEPENDENCIA_NO_DISPONIBLE' });

    await expect(cliente().get(ctx, '/api/gestion/v1/x')).rejects.toMatchObject({ codigo: 'DEPENDENCIA_NO_DISPONIBLE' });
    expect(ctx.estadisticas.llamadas).toBe(1);
  });

  it('al agotar el presupuesto responde CONSULTA_DEMASIADO_COMPLEJA sin llamar', async () => {
    gateway.registrar('/api/gestion/v1/x', { cuerpo: {} });
    const ctx = contexto();
    const c = cliente({ maximoLlamadas: 1 });
    await c.get(ctx, '/api/gestion/v1/x');
    await expect(c.get(ctx, '/api/gestion/v1/x')).rejects.toMatchObject({ codigo: 'CONSULTA_DEMASIADO_COMPLEJA' });
    expect(gateway.llamadas).toHaveLength(1);
  });
});

describe('TokenServicio', () => {
  it('una sola obtención para varias consultas, y el plazo vencido de una no corta a las demás', async () => {
    gateway.token = { demoraMs: 200 };
    const tokens = new TokenServicio(gateway.configuracion());
    const plazoA = new AbortController();
    const a = tokens.obtener(plazoA.signal);
    const b = tokens.obtener(new AbortController().signal);
    plazoA.abort(new PlazoConsultaVencido());
    await expect(a).rejects.toBeInstanceOf(PlazoConsultaVencido);
    await expect(b).resolves.toBe('token-servicio-1');
    expect(await tokens.obtener(new AbortController().signal)).toBe('token-servicio-1');
    expect(gateway.tokensEmitidos).toBe(1);
  });

  it('si Keycloak no responde, la obtención falla por su propio tiempo límite', async () => {
    gateway.token = { nuncaResponde: true };
    const inicio = Date.now();
    await expect(new TokenServicio(gateway.configuracion()).obtener(new AbortController().signal)).rejects.toThrow();
    expect(Date.now() - inicio).toBeLessThan(3000);
  });
});
