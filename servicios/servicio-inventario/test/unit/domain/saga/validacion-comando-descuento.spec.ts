import { validarComandoDescuento } from '../../../../src/domain/saga/validacion-comando-descuento';

const SAGA = '5d7c2a1e-0b3f-4c55-9a1e-3f2b1c0d9e8a';
const LABOR = '7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d';
const UREA = '0b6f1c6e-2f7a-4a7e-9a39-7d5a1c2b3d4e';
const GLIFOSATO = '1c7f2d7f-3a8b-4b8f-8b4a-8e6b2d3c4e5f';
const SOBRE = { version: 1, idCorrelacion: SAGA };

const datos = (cambios: Record<string, unknown> = {}) => ({
  idSaga: SAGA,
  idLabor: LABOR,
  items: [
    { idInsumo: UREA, cantidad: '100' },
    { idInsumo: GLIFOSATO, cantidad: '2.5' },
  ],
  ...cambios,
});

describe('validarComandoDescuento (RQ-SAG-02, paso 2)', () => {
  it('un comando correcto es válido', () => {
    expect(validarComandoDescuento(datos(), SOBRE)).toEqual({
      valido: true,
      comando: {
        idSaga: SAGA,
        idLabor: LABOR,
        items: [
          { idInsumo: UREA, cantidad: '100' },
          { idInsumo: GLIFOSATO, cantidad: '2.5' },
        ],
      },
    });
  });

  it.each([
    ['items vacío', datos({ items: [] }), SOBRE],
    ['items ausente', datos({ items: undefined }), SOBRE],
    ['idSaga que no es UUID', datos({ idSaga: 'S1' }), SOBRE],
    ['idLabor ausente', datos({ idLabor: undefined }), SOBRE],
    ['idCorrelacion distinto de idSaga', datos(), { version: 1, idCorrelacion: LABOR }],
    ['versión 2', datos(), { version: 2, idCorrelacion: SAGA }],
    ['datos nulos', null, SOBRE],
  ])('%s → inválido', (_caso, entrada, sobre) => {
    const resultado = validarComandoDescuento(entrada, sobre);
    expect(resultado.valido).toBe(false);
  });

  it.each([
    ['insumo repetido', [{ idInsumo: UREA, cantidad: '1' }, { idInsumo: UREA, cantidad: '2' }], UREA, '2'],
    ['cantidad como número JSON', [{ idInsumo: UREA, cantidad: 5 }], UREA, '5'],
    ['cantidad 0', [{ idInsumo: UREA, cantidad: '0.000' }], UREA, '0.000'],
    ['cantidad negativa', [{ idInsumo: UREA, cantidad: '-1' }], UREA, '-1'],
    ['cantidad con 4 decimales', [{ idInsumo: UREA, cantidad: '1.2345' }], UREA, '1.2345'],
    ['idInsumo que no es UUID', [{ idInsumo: 'urea', cantidad: '1' }], 'urea', '1'],
  ])('%s → inválido, con el ítem en insumosAfectados', (_caso, items, idInsumo, cantidad) => {
    const resultado = validarComandoDescuento(datos({ items }), SOBRE);
    expect(resultado).toMatchObject({
      valido: false,
      idSaga: SAGA,
      idLabor: LABOR,
      insumosAfectados: [{ idInsumo, cantidadSolicitada: cantidad, stockDisponible: null }],
    });
  });
});
