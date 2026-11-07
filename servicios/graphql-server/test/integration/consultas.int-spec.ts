import { crearAplicacion, type Aplicacion } from '../../src/app';
import * as d from '../soporte/datos';
import { consultar, GatewaySimulado } from '../soporte/gateway-simulado';

let gateway: GatewaySimulado;
let aplicacion: Aplicacion;
let token: string;

beforeAll(async () => {
  gateway = await GatewaySimulado.iniciar();
  aplicacion = await crearAplicacion(gateway.configuracion());
  token = await gateway.firmar({ roles: ['gerencia'] });
});
afterAll(async () => {
  await aplicacion.detener();
  await gateway.detener();
});
beforeEach(() => gateway.reiniciar());

/** Historias 1, 2, 3, 4 y 5: valores idénticos a los de los servicios, en una sola respuesta. */
describe('consultas consolidadas', () => {
  it('tablero: campañas con parcela, cultivo, indicadores y costos, más el estado del inventario', async () => {
    gateway.registrar(`${d.G}/campanias`, { cuerpo: d.pagina([d.campania('c1'), d.campania('c2')]) });
    gateway.registrar(`${d.G}/parcelas/p1`, { cuerpo: d.parcela('p1') });
    gateway.registrar(`${d.G}/cultivos/cu1`, { cuerpo: d.cultivo('cu1') });
    for (const id of ['c1', 'c2']) {
      gateway.registrar(`${d.G}/campanias/${id}/indicadores`, { cuerpo: d.indicadores(id) });
      gateway.registrar(`${d.G}/campanias/${id}/costos`, { cuerpo: d.costos });
    }
    gateway.registrar(`${d.I}/estado-inventario`, { cuerpo: d.estadoInventario });

    const respuesta = await consultar(
      aplicacion.app,
      token,
      `query Tablero { campanias(filtro: { estado: EN_CURSO }) { total items { id superficieHectareas fechaInicio
        fechaInicioEjecucion parcela { nombre } cultivo { variedad }
        indicadores { costoTotal rendimientoPorHectarea motivosNoDisponible }
        costos { costoTotal subtotalesPorCategoria { categoria monto } } } }
        estadoInventario(soloStockBajo: true) { resumen { totalStockBajo } items { nombre stock stockBajo } } }`,
    );

    expect(respuesta.status).toBe(200);
    expect(respuesta.body.errors).toBeUndefined();
    const [c1] = respuesta.body.data.campanias.items;
    expect(c1).toEqual({
      id: 'c1',
      superficieHectareas: '25.5000',
      fechaInicio: '2026-11-15',
      fechaInicioEjecucion: '2026-11-16T12:00:00.123456Z',
      parcela: { nombre: 'Lote p1' },
      cultivo: { variedad: 'Munasqa' },
      indicadores: { costoTotal: '820.50', rendimientoPorHectarea: null, motivosNoDisponible: ['SIN_PRODUCCION'] },
      costos: {
        costoTotal: '2320.50',
        subtotalesPorCategoria: [
          { categoria: 'INSUMO', monto: '820.50' },
          { categoria: 'MANO_DE_OBRA', monto: '1500.00' },
          { categoria: 'MAQUINARIA', monto: '0.00' },
          { categoria: 'OTRO', monto: '0.00' },
        ],
      },
    });
    expect(respuesta.body.data.estadoInventario).toEqual({
      resumen: { totalStockBajo: 2 },
      items: [{ nombre: 'Glifosato', stock: '20.000', stockBajo: true }],
    });
    // Filtro reenviado con su nombre; la parcela repetida se consulta una sola vez; costos con tamanio=1.
    expect(gateway.llamadasA(`${d.G}/campanias`)[0].ruta).toContain('estado=EN_CURSO');
    expect(gateway.llamadasA(`${d.G}/parcelas/p1`)).toHaveLength(1);
    expect(gateway.llamadasA(`${d.G}/campanias/c1/costos`)[0].ruta).toContain('tamanio=1');
  });

  it('campania inexistente y producción no registrada responden null sin error; finalizadas con sus costos', async () => {
    gateway.registrar(`${d.G}/campanias/c1`, { cuerpo: d.campania('c1') });
    gateway.registrar(`${d.G}/campanias/c1/produccion`, { estado: 404, cuerpo: { codigo: 'PRODUCCION_NO_REGISTRADA' } });
    gateway.registrar(`${d.G}/campanias/historicos`, { cuerpo: d.pagina([d.historico]) });

    const respuesta = await consultar(
      aplicacion.app,
      token,
      `{ existe: campania(id: "c1") { nombre produccion { cantidad } } noExiste: campania(id: "c404") { id }
         campaniasFinalizadas(filtro: { idCultivo: "cu1" }) { items { nombreParcela produccion rendimientoPorHectarea
           costosPorCategoria { categoria monto } } } }`,
    );

    expect(respuesta.body.errors).toBeUndefined();
    expect(respuesta.body.data.existe).toEqual({ nombre: 'Soya verano c1', produccion: null });
    expect(respuesta.body.data.noExiste).toBeNull();
    expect(respuesta.body.data.campaniasFinalizadas.items[0]).toMatchObject({
      nombreParcela: 'Lote Norte',
      produccion: '76500.00',
      rendimientoPorHectarea: '3000.00',
    });
    expect(respuesta.body.data.campaniasFinalizadas.items[0].costosPorCategoria[0]).toEqual({
      categoria: 'INSUMO',
      monto: '20000.00',
    });
  });

  it('labores de una campaña con sus insumos, cursor y la validación de operaciones reenviada', async () => {
    gateway.registrar(`${d.G}/campanias/c1`, { cuerpo: d.campania('c1') });
    gateway.registrar(`${d.O}/labores`, (llamada) =>
      llamada.ruta.includes('idCampania=c1')
        ? { cuerpo: { items: [d.labor('l1')], siguienteCursor: 'cur-2' } }
        : { estado: 400, cuerpo: { codigo: 'DATOS_INVALIDOS', detalles: ['falta idCampania, idResponsable o estado'] } },
    );
    gateway.registrar(`${d.I}/insumos/i1`, { cuerpo: d.insumo('i1') });

    const respuesta = await consultar(
      aplicacion.app,
      token,
      `{ campania(id: "c1") { labores(limite: 10) { siguienteCursor items { estado responsable { nombre }
           insumos { cantidad insumo { nombre costoUnitario } } } } }
         sinFiltro: labores(filtro: {}) { items { id } } }`,
    );

    expect(respuesta.body.data.campania.labores).toEqual({
      siguienteCursor: 'cur-2',
      items: [
        {
          estado: 'CONFIRMADA',
          responsable: { nombre: 'Ana Quispe' },
          insumos: [{ cantidad: '100.000', insumo: { nombre: 'Urea i1', costoUnitario: '4.8500' } }],
        },
      ],
    });
    const deLaCampania = gateway.llamadasA(`${d.O}/labores`).find((l) => l.ruta.includes('idCampania=c1'));
    expect(deLaCampania?.ruta).toContain('limite=10');
    expect(respuesta.body.data.sinFiltro).toBeNull();
    expect(respuesta.body.errors[0].extensions).toMatchObject({
      codigo: 'DATOS_INVALIDOS',
      detalles: ['falta idCampania, idResponsable o estado'],
    });
  });

  it('predicciones de una campaña junto a sus indicadores, y análisis con la campaña de cada anomalía', async () => {
    gateway.registrar(`${d.G}/campanias/c1`, { cuerpo: d.campania('c1') });
    gateway.registrar(`${d.G}/campanias/c1/indicadores`, { cuerpo: { ...d.indicadores('c1'), rendimientoPorHectarea: '3000.00' } });
    gateway.registrar(`${d.IA}/predicciones`, { cuerpo: { ...d.pagina([d.prediccion]), tamanio: 5 } });
    gateway.registrar(`${d.IA}/analisis/an1`, { cuerpo: d.analisis });
    gateway.registrar(`${d.IA}/analisis`, { cuerpo: d.pagina([]) });

    const respuesta = await consultar(
      aplicacion.app,
      token,
      `{ campania(id: "c1") { indicadores { rendimientoPorHectarea } predicciones { items { rendimientoEstimado
           rendimientoReal intervalo { minimo } advertencias { codigo } costosPorHectarea { categoria monto } orientativo aviso } } }
         analisisPorId(id: "an1") { anomalias { nombreParcela campania { nombre } } orientativo }
         analisis { total items { id } } }`,
    );

    expect(respuesta.body.errors).toBeUndefined();
    const { campania, analisisPorId, analisis } = respuesta.body.data;
    expect(campania.indicadores.rendimientoPorHectarea).toBe('3000.00');
    expect(campania.predicciones.items[0]).toMatchObject({
      rendimientoEstimado: '3120.40',
      rendimientoReal: '3000.00',
      intervalo: { minimo: '2810.00' },
      advertencias: [{ codigo: 'FUERA_DE_RANGO' }],
      orientativo: true,
    });
    expect(campania.predicciones.items[0].aviso).toContain('orientativa');
    expect(gateway.llamadasA(`${d.IA}/predicciones`)[0].ruta).toContain('idCampania=c1');
    expect(analisisPorId).toEqual({
      anomalias: [{ nombreParcela: 'Lote Norte', campania: { nombre: 'Soya verano c1' } }],
      orientativo: true,
    });
    expect(analisis).toEqual({ total: 0, items: [] });
  });
});
