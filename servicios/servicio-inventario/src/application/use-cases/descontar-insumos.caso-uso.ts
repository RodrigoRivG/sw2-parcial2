import { TipoMovimiento } from '../../domain/movement/tipo-movimiento.enum';
import {
  CodigoRechazoSaga,
  InsumoAfectado,
  ItemDescontado,
  RespuestaDescuento,
  SagaProcesada,
} from '../../domain/saga/saga-procesada.entidad';
import {
  ItemComandoDescuento,
  validarComandoDescuento,
} from '../../domain/saga/validacion-comando-descuento';
import { Cantidad } from '../../domain/shared/cantidad.vo';
import { Decimal } from '../../domain/shared/decimal';
import { Dinero } from '../../domain/shared/dinero.vo';
import { Insumo } from '../../domain/supply/insumo.entidad';
import { Reloj } from '../ports/reloj.puerto';
import { RepositorioInsumo } from '../ports/repositorio-insumo.puerto';
import { RepositorioSagaProcesada } from '../ports/repositorio-saga-procesada.puerto';
import { UnidadTrabajo } from '../ports/unidad-trabajo.puerto';
import { RegistrarMovimientoCasoUso } from './registrar-movimiento.caso-uso';
import {
  ResultadoComandoSaga,
  SobreComandoSaga,
  aRespuestaDescuento,
} from './respuestas-saga';

/**
 * `DescontarInsumos` (CU-08, RF-10). Todo o nada: si un insumo no existe o no alcanza, no se descuenta
 * ninguno (RN-04). Idempotente por `idSaga` (RN-09): repite la primera respuesta aunque cambie el costo.
 */
export class DescontarInsumosCasoUso {
  constructor(
    private readonly insumos: RepositorioInsumo,
    private readonly sagas: RepositorioSagaProcesada,
    private readonly registrarMovimiento: RegistrarMovimientoCasoUso,
    private readonly unidadTrabajo: UnidadTrabajo,
    private readonly reloj: Reloj,
  ) {}

  async ejecutar(datos: unknown, sobre: SobreComandoSaga): Promise<ResultadoComandoSaga> {
    const validacion = validarComandoDescuento(datos, sobre);
    if (!validacion.valido) {
      // Formato inválido: se responde sin guardar resultado (RQ-SAG-02, paso 2).
      return {
        respuesta: aRespuestaDescuento(validacion.idSaga, validacion.idLabor, {
          tipo: 'InsumosRechazados',
          codigo: 'DATOS_INVALIDOS',
          motivo: validacion.motivo,
          insumosAfectados: validacion.insumosAfectados,
        }),
        insumosAfectados: [],
      };
    }
    const { idSaga, idLabor, items } = validacion.comando;

    return this.unidadTrabajo.ejecutar(async () => {
      const ahora = this.reloj.ahora();
      const saga = await this.sagas.obtenerParaProcesar(idSaga, idLabor, ahora);
      const decision = saga.decidirDescuento();
      if (decision === 'REPETIR' && saga.descuento) {
        return {
          respuesta: aRespuestaDescuento(idSaga, idLabor, saga.descuento),
          insumosAfectados: [],
          advertencia: difiereDelOriginal(saga.descuento, items)
            ? `DescontarInsumos repetido con otros items para la saga ${idSaga}; se responde el resultado original.`
            : undefined,
        };
      }
      if (decision === 'RECHAZAR_COMPENSADA') {
        return {
          respuesta: aRespuestaDescuento(idSaga, idLabor, {
            tipo: 'InsumosRechazados',
            codigo: 'SAGA_COMPENSADA',
            motivo: 'La saga ya fue compensada; el descuento no se aplica.',
            insumosAfectados: [],
          }),
          insumosAfectados: [],
        };
      }

      const rechazo = await this.buscarRechazo(items);
      if (rechazo) {
        return this.guardar(saga, rechazo, ahora, []);
      }

      const descontados: ItemDescontado[] = [];
      for (const item of items) {
        // Si otra operación ganó la carrera, el error (STOCK_INSUFICIENTE) aborta la transacción y el
        // consumidor reintenta el comando: la nueva lectura decide con el stock actual.
        const movimiento = await this.registrarMovimiento.registrarDentroDeTransaccion(
          {
            idInsumo: item.idInsumo,
            tipo: TipoMovimiento.SALIDA,
            cantidad: item.cantidad,
            motivo: `Labor ${idLabor}`,
            idSaga,
            idLabor,
          },
          sobre.origen,
          'DESCONTAR_INSUMOS_SAGA',
        );
        descontados.push({
          idInsumo: item.idInsumo,
          cantidad: movimiento.cantidad,
          costoUnitario: movimiento.costoUnitario,
        });
      }
      // Precisión completa y redondeo final a 2 decimales, mitad hacia arriba (constitución §5).
      const costoTotal = descontados
        .reduce((total, item) => total.sumar(item.costoUnitario.multiplicar(item.cantidad)), Dinero.cero())
        .redondearA2();
      return this.guardar(
        saga,
        { tipo: 'InsumosDescontados', costoTotal, items: descontados },
        ahora,
        items.map((item) => item.idInsumo),
      );
    });
  }

  /** RQ-SAG-02, pasos 4 a 6, en ese orden de prioridad. */
  private async buscarRechazo(items: ItemComandoDescuento[]): Promise<RespuestaDescuento | null> {
    const leidos = new Map<string, Insumo | null>();
    for (const item of items) {
      leidos.set(item.idInsumo, await this.insumos.buscarPorId(item.idInsumo));
    }
    const afectado = (item: ItemComandoDescuento, insumo: Insumo | null): InsumoAfectado => ({
      idInsumo: item.idInsumo,
      cantidadSolicitada: new Decimal(item.cantidad).toFixed(3),
      stockDisponible: insumo ? insumo.stock.aTexto() : null,
    });
    const rechazar = (
      codigo: CodigoRechazoSaga,
      motivo: string,
      filtro: (item: ItemComandoDescuento, insumo: Insumo | null) => boolean,
    ): RespuestaDescuento | null => {
      const afectados = items
        .filter((item) => filtro(item, leidos.get(item.idInsumo) ?? null))
        .map((item) => afectado(item, leidos.get(item.idInsumo) ?? null));
      return afectados.length > 0
        ? { tipo: 'InsumosRechazados', codigo, motivo, insumosAfectados: afectados }
        : null;
    };

    return (
      rechazar('INSUMO_NO_ENCONTRADO', 'Uno o más insumos no existen.', (_i, insumo) => !insumo) ??
      rechazar(
        'DATOS_INVALIDOS',
        'Los insumos con unidad UNIDAD solo admiten cantidades enteras.',
        (item, insumo) => insumo !== null && !esCantidadValida(item.cantidad, insumo),
      ) ??
      rechazar(
        'STOCK_INSUFICIENTE',
        'No hay stock suficiente de uno o más insumos.',
        (item, insumo) =>
          insumo !== null && !Cantidad.de(item.cantidad, insumo.unidad).esMenorOIgualQue(insumo.stock),
      )
    );
  }

  private async guardar(
    saga: SagaProcesada,
    respuesta: RespuestaDescuento,
    ahora: Date,
    insumosAfectados: string[],
  ): Promise<ResultadoComandoSaga> {
    saga.registrarDescuento(respuesta, ahora);
    await this.sagas.guardar(saga);
    return {
      respuesta: aRespuestaDescuento(saga.idSaga, saga.idLabor, respuesta),
      insumosAfectados,
    };
  }
}

function esCantidadValida(cantidad: string, insumo: Insumo): boolean {
  try {
    Cantidad.de(cantidad, insumo.unidad);
    return true;
  } catch {
    return false;
  }
}

/** Solo se puede comparar contra un descuento aplicado, que guarda sus items. */
function difiereDelOriginal(original: RespuestaDescuento, items: ItemComandoDescuento[]): boolean {
  if (original.tipo !== 'InsumosDescontados') {
    return false;
  }
  const clave = (pares: [string, string][]) =>
    pares
      .map(([id, cantidad]) => `${id}:${new Decimal(cantidad).toFixed(3)}`)
      .sort()
      .join('|');
  return (
    clave(original.items.map((i) => [i.idInsumo, i.cantidad.valor.toString()])) !==
    clave(items.map((i) => [i.idInsumo, i.cantidad]))
  );
}
