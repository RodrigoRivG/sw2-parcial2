import {
  DURACION_RESERVA_ALERTA_MS,
  debeAlertar,
} from '../../domain/supply/politica-stock-bajo';
import { PublicadorEventos } from '../ports/publicador-eventos.puerto';
import { Reloj } from '../ports/reloj.puerto';
import { RepositorioInsumo } from '../ports/repositorio-insumo.puerto';

export const ROUTING_KEY_STOCK_BAJO = 'inventario.stock.bajo';
export const TIPO_EVENTO_STOCK_BAJO = 'StockBajo';

export type ResultadoAlerta = 'PUBLICADA' | 'NO_CORRESPONDE' | 'RESERVADA_POR_OTRO' | 'FALLIDA';

export interface ResultadoEvaluacion {
  idInsumo: string;
  resultado: ResultadoAlerta;
  error?: unknown;
}

/**
 * RN-05: tras el commit de un movimiento, publica `inventario.stock.bajo` si corresponde.
 * La alerta se reserva antes de publicar (una sola por insumo aunque haya movimientos simultáneos)
 * y la fecha se guarda solo si el broker confirmó (constitución §5). Nunca lanza: informa cada
 * resultado para que quien la llama registre los fallos sin afectar al movimiento.
 */
export class EvaluarStockBajoCasoUso {
  constructor(
    private readonly insumos: RepositorioInsumo,
    private readonly publicador: PublicadorEventos,
    private readonly reloj: Reloj,
  ) {}

  async ejecutar(idsInsumo: string[], idCorrelacion?: string): Promise<ResultadoEvaluacion[]> {
    const resultados: ResultadoEvaluacion[] = [];
    for (const idInsumo of new Set(idsInsumo)) {
      try {
        resultados.push({ idInsumo, resultado: await this.evaluar(idInsumo, idCorrelacion) });
      } catch (error) {
        resultados.push({ idInsumo, resultado: 'FALLIDA', error });
      }
    }
    return resultados;
  }

  private async evaluar(idInsumo: string, idCorrelacion?: string): Promise<ResultadoAlerta> {
    const insumo = await this.insumos.buscarPorId(idInsumo);
    const ahora = this.reloj.ahora();
    if (insumo === null || !debeAlertar(insumo, ahora)) {
      return 'NO_CORRESPONDE';
    }
    const reservada = await this.insumos.reservarAlerta(
      idInsumo,
      insumo.fechaUltimaAlerta,
      ahora,
      new Date(ahora.getTime() + DURACION_RESERVA_ALERTA_MS),
    );
    if (!reservada) {
      return 'RESERVADA_POR_OTRO';
    }
    try {
      await this.publicador.publicarEvento({
        routingKey: ROUTING_KEY_STOCK_BAJO,
        tipo: TIPO_EVENTO_STOCK_BAJO,
        idCorrelacion,
        datos: {
          idInsumo: insumo.id,
          nombre: insumo.nombre,
          stock: insumo.stock.aTexto(),
          nivelMinimo: insumo.nivelMinimo.aTexto(),
          unidad: insumo.unidad,
        },
      });
    } catch (error) {
      // La próxima evaluación vuelve a intentarlo; si esto también falla, la reserva vence sola.
      await this.insumos.liberarReserva(idInsumo).catch(() => undefined);
      throw error;
    }
    await this.insumos.confirmarAlerta(idInsumo, ahora);
    return 'PUBLICADA';
  }
}
