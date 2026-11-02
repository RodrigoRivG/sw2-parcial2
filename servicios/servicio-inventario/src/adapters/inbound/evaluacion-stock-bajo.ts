import { Inject, Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { EvaluarStockBajoCasoUso } from '../../application/use-cases/evaluar-stock-bajo.caso-uso';
import { idCorrelacionActual } from '../contexto-correlacion';

/**
 * Lanza la evaluación de stock bajo después del commit, sin hacer esperar la respuesta del movimiento,
 * y registra en el log las alertas que no se pudieron publicar (RQ-SBJ-05). La usan el controlador
 * REST y, más adelante, el consumidor de la Saga.
 */
@Injectable()
export class EvaluacionStockBajo implements OnModuleDestroy {
  private readonly logger = new Logger(EvaluacionStockBajo.name);
  private readonly pendientes = new Set<Promise<void>>();

  constructor(
    @Inject(EvaluarStockBajoCasoUso) private readonly evaluarStockBajo: EvaluarStockBajoCasoUso,
  ) {}

  programar(idsInsumo: string[]): void {
    const evaluacion = this.evaluar(idsInsumo, idCorrelacionActual());
    this.pendientes.add(evaluacion);
    void evaluacion.finally(() => this.pendientes.delete(evaluacion));
  }

  /** Para los tests y el apagado ordenado: espera las evaluaciones en curso. */
  async esperarPendientes(): Promise<void> {
    await Promise.allSettled([...this.pendientes]);
  }

  async onModuleDestroy(): Promise<void> {
    await this.esperarPendientes();
  }

  private async evaluar(idsInsumo: string[], idCorrelacion?: string): Promise<void> {
    const resultados = await this.evaluarStockBajo.ejecutar(idsInsumo, idCorrelacion);
    for (const { idInsumo, resultado, error } of resultados) {
      if (resultado === 'FALLIDA') {
        this.logger.error(
          `No se pudo publicar la alerta de stock bajo del insumo ${idInsumo}; se reintentará en el próximo movimiento: ${
            error instanceof Error ? error.message : String(error)
          }`,
        );
      }
    }
  }
}
