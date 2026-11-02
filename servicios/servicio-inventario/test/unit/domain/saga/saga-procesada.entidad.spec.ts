import { ResultadoSagaProcesada } from '../../../../src/domain/saga/resultado-saga-procesada.enum';
import {
  RespuestaDescuento,
  SagaProcesada,
} from '../../../../src/domain/saga/saga-procesada.entidad';
import { Dinero } from '../../../../src/domain/shared/dinero.vo';

const AHORA = new Date('2026-11-02T10:00:00Z');
const DESCONTADO: RespuestaDescuento = {
  tipo: 'InsumosDescontados',
  costoTotal: Dinero.costoUnitario('580.5'),
  items: [],
};
const RECHAZADO: RespuestaDescuento = {
  tipo: 'InsumosRechazados',
  codigo: 'STOCK_INSUFICIENTE',
  motivo: 'No alcanza',
  insumosAfectados: [],
};
const SIN_EFECTO = { sinEfecto: true, items: [] };

const nueva = () => SagaProcesada.nueva('s-1', 'l-1', AHORA);

describe('SagaProcesada — RQ-SAG-05 (DescontarInsumos)', () => {
  it('sin procesar → PROCESAR', () => {
    expect(nueva().decidirDescuento()).toBe('PROCESAR');
  });

  it.each([
    ['DESCONTADO', DESCONTADO, ResultadoSagaProcesada.DESCONTADO],
    ['RECHAZADO', RECHAZADO, ResultadoSagaProcesada.RECHAZADO],
  ])('con descuento %s guardado → REPETIR', (_caso, respuesta, resultado) => {
    const saga = nueva();
    saga.registrarDescuento(respuesta, AHORA);
    expect(saga.resultado).toBe(resultado);
    expect(saga.decidirDescuento()).toBe('REPETIR');
  });

  it('RESTAURADO después de descontar → REPETIR (la respuesta original del descuento)', () => {
    const saga = nueva();
    saga.registrarDescuento(DESCONTADO, AHORA);
    saga.registrarRestauracion({ sinEfecto: false, items: [] }, AHORA);
    expect(saga.resultado).toBe(ResultadoSagaProcesada.RESTAURADO);
    expect(saga.decidirDescuento()).toBe('REPETIR');
    expect(saga.descuento).toBe(DESCONTADO);
  });

  it('RESTAURADO sin descuento previo → RECHAZAR_COMPENSADA', () => {
    const saga = nueva();
    saga.registrarRestauracion(SIN_EFECTO, AHORA);
    expect(saga.resultado).toBe(ResultadoSagaProcesada.RESTAURADO);
    expect(saga.decidirDescuento()).toBe('RECHAZAR_COMPENSADA');
  });
});

describe('SagaProcesada — RQ-SAG-07 (RestaurarInsumos)', () => {
  it('DESCONTADO → RESTAURAR', () => {
    const saga = nueva();
    saga.registrarDescuento(DESCONTADO, AHORA);
    expect(saga.decidirRestauracion()).toBe('RESTAURAR');
  });

  it('sin procesar → SIN_EFECTO, y queda RESTAURADO', () => {
    const saga = nueva();
    expect(saga.decidirRestauracion()).toBe('SIN_EFECTO');
    saga.registrarRestauracion(SIN_EFECTO, AHORA);
    expect(saga.resultado).toBe(ResultadoSagaProcesada.RESTAURADO);
  });

  it('RECHAZADO → SIN_EFECTO, y conserva RECHAZADO', () => {
    const saga = nueva();
    saga.registrarDescuento(RECHAZADO, AHORA);
    expect(saga.decidirRestauracion()).toBe('SIN_EFECTO');
    saga.registrarRestauracion(SIN_EFECTO, AHORA);
    expect(saga.resultado).toBe(ResultadoSagaProcesada.RECHAZADO);
  });

  it('con restauración guardada → REPETIR', () => {
    const saga = nueva();
    saga.registrarRestauracion(SIN_EFECTO, new Date('2026-11-03T00:00:00Z'));
    expect(saga.decidirRestauracion()).toBe('REPETIR');
    expect(saga.fechaProcesamiento).toEqual(AHORA);
    expect(saga.fechaActualizacion).toEqual(new Date('2026-11-03T00:00:00Z'));
    expect([saga.idSaga, saga.idLabor]).toEqual(['s-1', 'l-1']);
  });
});
