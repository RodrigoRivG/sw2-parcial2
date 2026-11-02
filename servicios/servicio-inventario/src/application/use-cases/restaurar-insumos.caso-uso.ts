import { TipoMovimiento } from '../../domain/movement/tipo-movimiento.enum';
import {
  ItemRestaurado,
  RespuestaRestauracion,
} from '../../domain/saga/saga-procesada.entidad';
import { esUuid } from '../../domain/saga/validacion-comando-descuento';
import { Reloj } from '../ports/reloj.puerto';
import { RepositorioMovimiento } from '../ports/repositorio-movimiento.puerto';
import { RepositorioSagaProcesada } from '../ports/repositorio-saga-procesada.puerto';
import { UnidadTrabajo } from '../ports/unidad-trabajo.puerto';
import { RegistrarMovimientoCasoUso } from './registrar-movimiento.caso-uso';
import {
  ComandoNoProcesable,
  ResultadoComandoSaga,
  SobreComandoSaga,
  aRespuestaRestauracion,
} from './respuestas-saga';

/**
 * `RestaurarInsumos` (compensación, RN-08). Devuelve exactamente lo que descontó ese `idSaga`, leído de
 * sus movimientos y no del comando. Si llega antes que el descuento, deja el `idSaga` restaurado para que
 * el descuento tardío se rechace con `SAGA_COMPENSADA` (constitución §5). Idempotente (RN-09).
 */
export class RestaurarInsumosCasoUso {
  constructor(
    private readonly movimientos: RepositorioMovimiento,
    private readonly sagas: RepositorioSagaProcesada,
    private readonly registrarMovimiento: RegistrarMovimientoCasoUso,
    private readonly unidadTrabajo: UnidadTrabajo,
    private readonly reloj: Reloj,
  ) {}

  async ejecutar(datos: unknown, sobre: SobreComandoSaga): Promise<ResultadoComandoSaga> {
    const { idSaga, idLabor } = (datos ?? {}) as Record<string, unknown>;
    if (sobre.version !== 1 || !esUuid(idSaga) || !esUuid(idLabor) || sobre.idCorrelacion !== idSaga) {
      throw new ComandoNoProcesable(
        'RestaurarInsumos necesita version 1, idSaga e idLabor UUID e idCorrelacion igual a idSaga.',
      );
    }

    return this.unidadTrabajo.ejecutar(async () => {
      const ahora = this.reloj.ahora();
      const saga = await this.sagas.obtenerParaProcesar(idSaga, idLabor, ahora);
      const advertencia =
        saga.idLabor !== idLabor
          ? `RestaurarInsumos con idLabor ${idLabor} distinto del guardado (${saga.idLabor}) para la saga ${idSaga}; manda el idSaga.`
          : undefined;
      const decision = saga.decidirRestauracion();
      if (decision === 'REPETIR' && saga.restauracion) {
        return {
          respuesta: aRespuestaRestauracion(idSaga, idLabor, saga.restauracion),
          insumosAfectados: [],
          advertencia,
        };
      }

      let respuesta: RespuestaRestauracion = { sinEfecto: true, items: [] };
      if (decision === 'RESTAURAR') {
        const items: ItemRestaurado[] = [];
        for (const salida of await this.movimientos.listarPorSaga(idSaga, TipoMovimiento.SALIDA)) {
          await this.registrarMovimiento.registrarDentroDeTransaccion(
            {
              idInsumo: salida.idInsumo,
              tipo: TipoMovimiento.ENTRADA,
              cantidad: salida.cantidad.valor,
              motivo: `Compensación de saga ${idSaga}`,
              idSaga,
              idLabor: saga.idLabor,
              // El costo de la salida original, aunque el costo unitario haya cambiado después.
              costoUnitario: salida.costoUnitario,
            },
            sobre.origen,
            'RESTAURAR_INSUMOS_SAGA',
          );
          items.push({ idInsumo: salida.idInsumo, cantidad: salida.cantidad });
        }
        respuesta = { sinEfecto: false, items };
      }
      saga.registrarRestauracion(respuesta, ahora);
      await this.sagas.guardar(saga);
      return {
        respuesta: aRespuestaRestauracion(idSaga, idLabor, respuesta),
        insumosAfectados: respuesta.items.map((item) => item.idInsumo),
        advertencia,
      };
    });
  }
}
