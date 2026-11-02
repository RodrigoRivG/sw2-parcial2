import request from 'supertest';
import { EvaluacionStockBajo } from '../../../src/adapters/inbound/evaluacion-stock-bajo';
import { Cantidad } from '../../../src/domain/shared/cantidad.vo';
import { estaEnStockBajo } from '../../../src/domain/supply/politica-stock-bajo';
import { UnidadMedida } from '../../../src/domain/supply/unidad-medida.enum';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba, datosInsumo } from '../soporte/aplicacion-prueba';

interface EstadoInsumo {
  idInsumo: string;
  nombre: string;
  stock: string;
  nivelMinimo: string;
  stockBajo: boolean;
  fechaUltimaAlerta: string | null;
}

describe('Estado del inventario (spec-estado-inventario.md, RF-33)', () => {
  let ap: AplicacionPrueba;
  let admin: string;
  let gerencia: string;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    admin = await ap.tokens.bearer(['administrador']);
    gerencia = await ap.tokens.bearer(['gerencia']);
  });

  afterAll(() => ap.cerrar());

  beforeEach(async () => {
    for (const coleccion of ['insumos', 'movimientos_inventario', 'registros_auditoria']) {
      await ap.conexion.collection(coleccion).deleteMany({});
    }
  });

  async function crearInsumo(
    nombre: string,
    stock: string,
    nivelMinimo: string,
    cambios: Record<string, unknown> = {},
  ): Promise<string> {
    const respuesta = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', admin)
      .send(datosInsumo({ nombre, stockInicial: stock, nivelMinimo, ...cambios }));
    expect(respuesta.status).toBe(201);
    // El stock inicial es un movimiento: si queda bajo el mínimo, se publica la alerta.
    await ap.app.get(EvaluacionStockBajo).esperarPendientes();
    return respuesta.body.id;
  }

  /** Los tres insumos de la Historia 1. */
  async function cargarEjemplo() {
    await crearInsumo('Urea', '40', '50');
    await crearInsumo('Glifosato', '20', '20', { categoria: 'FITOSANITARIO', unidad: 'LITRO' });
    await crearInsumo('Semilla de maíz', '300', '100', { categoria: 'SEMILLA' });
  }

  const consultar = (consulta = '', autorizacion = gerencia) =>
    request(ap.servidor)
      .get(`${PREFIJO}/estado-inventario${consulta ? `?${consulta}` : ''}`)
      .set('Authorization', autorizacion);

  const nombres = (items: EstadoInsumo[]) => items.map((i) => i.nombre);

  describe('Historia 1 — Ver qué insumos están en stock bajo', () => {
    it('escenarios 1 y 2: stock bajo primero (por nombre), luego el resto; resumen 3 / 2', async () => {
      await cargarEjemplo();
      const respuesta = await consultar();
      expect(respuesta.status).toBe(200);
      expect(nombres(respuesta.body.items)).toEqual(['Glifosato', 'Urea', 'Semilla de maíz']);
      expect(respuesta.body.items.map((i: EstadoInsumo) => i.stockBajo)).toEqual([true, true, false]);
      expect(respuesta.body.items[0]).toEqual({
        idInsumo: expect.any(String),
        nombre: 'Glifosato',
        categoria: 'FITOSANITARIO',
        unidad: 'LITRO',
        stock: '20.000',
        nivelMinimo: '20.000',
        stockBajo: true,
        fechaUltimaAlerta: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/),
      });
      expect(respuesta.body.items[2].fechaUltimaAlerta).toBeNull();
      expect(respuesta.body.items[0]).not.toHaveProperty('costoUnitario');
      expect(respuesta.body).toMatchObject({
        resumen: { totalInsumos: 3, totalStockBajo: 2 },
        pagina: 0,
        tamanio: 20,
        total: 3,
      });
    });

    it('escenario 3: soloStockBajo=true devuelve solo esos, y el resumen cuenta todo', async () => {
      await cargarEjemplo();
      const respuesta = await consultar('soloStockBajo=true');
      expect(nombres(respuesta.body.items)).toEqual(['Glifosato', 'Urea']);
      expect(respuesta.body.total).toBe(2);
      expect(respuesta.body.resumen).toEqual({ totalInsumos: 3, totalStockBajo: 2 });
    });

    it('escenario 4: el filtro por categoría también acota el resumen', async () => {
      await cargarEjemplo();
      await crearInsumo('Fosfato diamónico', '500', '100');
      const respuesta = await consultar('categoria=FERTILIZANTE');
      expect(nombres(respuesta.body.items)).toEqual(['Urea', 'Fosfato diamónico']);
      expect(respuesta.body.resumen).toEqual({ totalInsumos: 2, totalStockBajo: 1 });
    });

    it('escenario 5: stock 0 con mínimo 0 está en stock bajo', async () => {
      await crearInsumo('Trampa de feromonas', '0', '0', { unidad: 'UNIDAD' });
      const [item] = (await consultar()).body.items;
      expect(item).toMatchObject({ stock: '0.000', nivelMinimo: '0.000', stockBajo: true });
    });

    it('escenario 6: muestra la fecha de la última alerta', async () => {
      const id = await crearInsumo('Urea', '40', '50');
      const guardada = await ap.conexion.collection('insumos').findOne({ _id: id as never });
      expect(guardada?.fecha_ultima_alerta).toBeInstanceOf(Date);
      const [item] = (await consultar()).body.items;
      expect(item.fechaUltimaAlerta).toBe(guardada?.fecha_ultima_alerta.toISOString());
    });
  });

  describe('Historia 2 — Leer el estado desde integraciones', () => {
    it('escenario 1: lectura_inventario recibe lo mismo que gerencia', async () => {
      await cargarEjemplo();
      const integracion = await consultar('', await ap.tokens.bearer(['lectura_inventario']));
      expect(integracion.status).toBe(200);
      expect(integracion.body).toEqual((await consultar()).body);
      expect((await consultar('', admin)).status).toBe(200);
    });

    it('escenario 2: solo tecnico_campo → 403 SIN_PERMISO', async () => {
      const respuesta = await consultar('', await ap.tokens.bearer(['tecnico_campo']));
      expect([respuesta.status, respuesta.body.codigo]).toEqual([403, 'SIN_PERMISO']);
    });
  });

  it('OpenAPI documenta el endpoint con sus respuestas', async () => {
    const { body } = await request(ap.servidor).get('/api-docs-json');
    const get = body.paths[`${PREFIJO}/estado-inventario`].get;
    expect(Object.keys(get.responses).sort()).toEqual(['200', '400', '401', '403']);
    expect(get.parameters.map((p: { name: string }) => p.name).sort()).toEqual([
      'categoria',
      'pagina',
      'soloStockBajo',
      'tamanio',
    ]);
  });

  describe('Casos borde y criterios de éxito', () => {
    it('página fuera de rango: lista vacía con el resumen y el total reales', async () => {
      await cargarEjemplo();
      const respuesta = await consultar('pagina=5');
      expect(respuesta.status).toBe(200);
      expect(respuesta.body.items).toEqual([]);
      expect(respuesta.body.total).toBe(3);
      expect(respuesta.body.resumen).toEqual({ totalInsumos: 3, totalStockBajo: 2 });
    });

    it('sin insumos: resumen en cero', async () => {
      const respuesta = await consultar();
      expect(respuesta.body).toMatchObject({
        items: [],
        total: 0,
        resumen: { totalInsumos: 0, totalStockBajo: 0 },
      });
    });

    it.each([
      ['categoría inválida', 'categoria=HERBICIDA'],
      ['soloStockBajo no booleano', 'soloStockBajo=si'],
      ['tamaño fuera de rango', 'tamanio=101'],
      ['página negativa', 'pagina=-1'],
    ])('%s → 400 DATOS_INVALIDOS', async (_caso, consulta) => {
      const respuesta = await consultar(consulta);
      expect([respuesta.status, respuesta.body.codigo]).toEqual([400, 'DATOS_INVALIDOS']);
    });

    it('cambiar el nivel mínimo con PUT cambia stockBajo en la siguiente consulta', async () => {
      const id = await crearInsumo('Semilla de soja', '80', '50', { categoria: 'SEMILLA' });
      expect((await consultar()).body.items[0].stockBajo).toBe(false);
      const actualizado = await request(ap.servidor)
        .put(`${PREFIJO}/insumos/${id}`)
        .set('Authorization', admin)
        .send(datosInsumo({ nombre: 'Semilla de soja', categoria: 'SEMILLA', nivelMinimo: '80', version: 0 }));
      expect(actualizado.status).toBe(200);
      expect((await consultar()).body.items[0].stockBajo).toBe(true);
    });

    it('CE-EST-02 y CE-EST-03: orden y resumen coinciden con la política del dominio y un conteo propio', async () => {
      const casos: [string, string][] = [
        ['10', '50'], ['50', '50'], ['50.001', '50'], ['0', '0'], ['0.001', '0'],
        ['99.999', '100'], ['100', '99.999'], ['7', '7'], ['3.5', '2'], ['0', '1'],
      ];
      for (const [indice, [stock, minimo]] of casos.entries()) {
        await crearInsumo(`Insumo ${String.fromCharCode(74 - indice)}`, stock, minimo);
      }
      const { body } = await consultar('tamanio=100');
      const items = body.items as EstadoInsumo[];
      const kg = (valor: string) => Cantidad.de(valor, UnidadMedida.KILOGRAMO);
      for (const item of items) {
        expect(item.stockBajo).toBe(estaEnStockBajo(kg(item.stock), kg(item.nivelMinimo)));
      }
      const esperadoBajos = casos.filter(([s, m]) => estaEnStockBajo(kg(s), kg(m))).length;
      expect(body.resumen).toEqual({ totalInsumos: casos.length, totalStockBajo: esperadoBajos });
      // Los de stock bajo van primero y, dentro de cada grupo, por nombre.
      const bajos = items.filter((i) => i.stockBajo);
      const resto = items.filter((i) => !i.stockBajo);
      expect(items).toEqual([...bajos, ...resto]);
      for (const grupo of [bajos, resto]) {
        expect(nombres(grupo)).toEqual([...nombres(grupo)].sort());
      }
    });
  });
});
