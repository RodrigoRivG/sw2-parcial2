import request from 'supertest';
import { crearAplicacion, type Aplicacion } from '../../src/app';
import * as d from '../soporte/datos';
import { consultar, GatewaySimulado } from '../soporte/gateway-simulado';

let gateway: GatewaySimulado;
let aplicacion: Aplicacion;
let token: string;

beforeAll(async () => {
  gateway = await GatewaySimulado.iniciar();
  aplicacion = await crearAplicacion(gateway.configuracion());
  token = await gateway.firmar();
});
afterAll(async () => {
  await aplicacion.detener();
  await gateway.detener();
});
beforeEach(() => gateway.reiniciar());

const codigos = (body: { errors?: { extensions: { codigo: string } }[] }) => body.errors?.map((e) => e.extensions.codigo);

/** Historia 7, correlación (historia 8) y rendimiento (CE-GQL-02). */
describe('resiliencia', () => {
  it('un servicio caído deja en null solo su parte; un 403 del servicio es ERROR_INTERNO', async () => {
    gateway.registrar(`${d.G}/campanias`, { cuerpo: d.pagina([d.campania('c1')]) });
    gateway.registrar(`${d.I}/estado-inventario`, { estado: 503 });
    gateway.registrar(`${d.O}/incidencias`, { estado: 403 });

    const respuesta = await consultar(
      aplicacion.app,
      token,
      '{ campanias { total } estadoInventario { total } incidencias(filtro: { idCampania: "c1" }) { siguienteCursor } }',
    );

    expect(respuesta.status).toBe(200);
    expect(respuesta.body.data).toEqual({ campanias: { total: 1 }, estadoInventario: null, incidencias: null });
    expect(codigos(respuesta.body)?.sort()).toEqual(['DEPENDENCIA_NO_DISPONIBLE', 'ERROR_INTERNO']);
  });

  it('el máximo de llamadas corta lo que excede con CONSULTA_DEMASIADO_COMPLEJA', async () => {
    const limitada = await crearAplicacion(gateway.configuracion({ maximoLlamadas: 2 }));
    gateway.registrar(`${d.G}/campanias`, { cuerpo: d.pagina([d.campania('c1', 'p1'), d.campania('c2', 'p2')]) });
    gateway.registrar(`${d.G}/parcelas/p1`, { cuerpo: d.parcela('p1') });
    gateway.registrar(`${d.G}/parcelas/p2`, { cuerpo: d.parcela('p2') });

    const respuesta = await consultar(limitada.app, token, '{ campanias { items { parcela { nombre } } } }');

    expect(codigos(respuesta.body)).toEqual(['CONSULTA_DEMASIADO_COMPLEJA']);
    expect(gateway.llamadas).toHaveLength(2);
    await limitada.detener();
  });

  it('escenarios 6 y 7: el plazo corta las llamadas lentas y responde a tiempo con los datos parciales', async () => {
    // Tiempos escalados (plazo de 900 ms): gestión y operaciones tardan 500 ms cada uno e inventario no responde.
    const conPlazo = await crearAplicacion(gateway.configuracion({ plazoConsultaMs: 900, tiempoLimiteLlamadaMs: 800 }));
    gateway.registrar(`${d.G}/campanias/c1`, { cuerpo: d.campania('c1'), demoraMs: 500 });
    gateway.registrar(`${d.O}/labores`, { cuerpo: { items: [d.labor('l1')], siguienteCursor: null }, demoraMs: 500 });
    gateway.registrar(`${d.I}/insumos/i1`, { nuncaResponde: true });
    gateway.jwks = { demoraMs: 300 }; // Escenario 7: claves fuera de caché; la validación cuenta dentro del plazo.
    const consulta = '{ campania(id: "c1") { nombre labores { items { insumos { insumo { nombre } } } } } }';

    const inicio = Date.now();
    const respuesta = await consultar(conPlazo.app, token, consulta);
    const duracion = Date.now() - inicio;

    expect(duracion).toBeLessThan(1100);
    expect(respuesta.body.data).toEqual({ campania: { nombre: 'Soya verano c1', labores: null } });
    expect(codigos(respuesta.body)).toEqual(['DEPENDENCIA_NO_DISPONIBLE']);
    expect(gateway.llamadasA(`${d.I}/insumos/i1`)).toHaveLength(0);
    await conPlazo.detener();
  });

  it('la readiness responde UP sin ningún servicio', async () => {
    gateway.jwks = { estado: 500 };
    for (const ruta of ['/salud', '/salud/liveness', '/salud/readiness']) {
      const respuesta = await request(aplicacion.app).get(ruta);
      expect(respuesta.status).toBe(200);
      expect(respuesta.body).toEqual({ estado: 'UP' });
    }
  });

  it('propaga el X-Correlation-Id a cada llamada y a los errores, y escribe un log de acceso sin token ni consulta', async () => {
    const salida = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    gateway.registrar(`${d.G}/campanias`, { cuerpo: d.pagina([d.campania('c1')]) });
    gateway.registrar(`${d.G}/campanias/c1/indicadores`, { estado: 503 });

    const recibido = await consultar(aplicacion.app, token, 'query Tablero { campanias { items { indicadores { costoTotal } } } }', {
      'X-Correlation-Id': 'abc-123',
    });
    const generado = await consultar(aplicacion.app, token, '{ campanias { total } }', { 'X-Correlation-Id': 'no valido!' });
    await new Promise((listo) => setTimeout(listo, 50)); // El log de acceso se escribe al cerrar la respuesta.
    const escrito = salida.mock.calls.map(([texto]) => String(texto)); // mockRestore borra las llamadas
    salida.mockRestore();

    expect(recibido.headers['x-correlation-id']).toBe('abc-123');
    expect(recibido.body.errors[0].extensions.idCorrelacion).toBe('abc-123');
    expect(gateway.llamadas.slice(0, 2).map((l) => l.headers['x-correlation-id'])).toEqual(['abc-123', 'abc-123']);
    expect(generado.headers['x-correlation-id']).toMatch(/^[0-9a-f-]{36}$/);

    const lineas = escrito.filter((l) => l.startsWith('{'));
    const acceso = lineas.map((l) => JSON.parse(l)).find((l) => l.mensaje === 'Solicitud atendida' && l.idCorrelacion === 'abc-123');
    expect(acceso).toMatchObject({
      ruta: '/api/graphql',
      operacion: 'Tablero',
      estado: 200,
      cantidadLlamadas: 2,
      cantidadErrores: 1,
      sub: 'usuario-123',
    });
    // Ni el token ni el texto de la consulta (costoTotal solo aparece en ella).
    expect(lineas.join('')).not.toContain(token);
    expect(lineas.join('')).not.toContain('costoTotal');
  });

  it('CE-GQL-02: el tablero de 20 campañas, con 200 ms por respuesta, llega en menos de 1,5 s', async () => {
    const ids = Array.from({ length: 20 }, (_, i) => `c${i}`);
    gateway.registrar(`${d.G}/campanias`, { cuerpo: d.pagina(ids.map((id) => d.campania(id, `p${id}`, `cu${id}`))), demoraMs: 200 });
    for (const id of ids) {
      gateway.registrar(`${d.G}/parcelas/p${id}`, { cuerpo: d.parcela(`p${id}`), demoraMs: 200 });
      gateway.registrar(`${d.G}/cultivos/cu${id}`, { cuerpo: d.cultivo(`cu${id}`), demoraMs: 200 });
      gateway.registrar(`${d.G}/campanias/${id}/indicadores`, { cuerpo: d.indicadores(id), demoraMs: 200 });
    }
    gateway.registrar(`${d.I}/estado-inventario`, { cuerpo: d.estadoInventario, demoraMs: 200 });

    const inicio = Date.now();
    const respuesta = await consultar(
      aplicacion.app,
      token,
      `{ campanias { items { parcela { nombre } cultivo { nombre } indicadores { costoTotal } } }
         estadoInventario { resumen { totalStockBajo } } }`,
    );

    expect(respuesta.body.errors).toBeUndefined();
    expect(respuesta.body.data.campanias.items).toHaveLength(20);
    expect(Date.now() - inicio).toBeLessThan(1500);
  });
});
