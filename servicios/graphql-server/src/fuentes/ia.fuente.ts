import type { Dato } from './cargador';
import type { ClienteGateway, ContextoLlamada, Parametros } from './cliente-gateway';

const BASE = '/api/ia/v1';

/** Lecturas de servicio-ia (rol `lectura_ia`): predicciones y análisis ya guardados. */
export class FuenteIa {
  constructor(
    private readonly cliente: ClienteGateway,
    private readonly contexto: ContextoLlamada,
  ) {}

  listar(recurso: 'predicciones' | 'analisis', parametros: Parametros) {
    return this.cliente.get<Dato>(this.contexto, `${BASE}/${recurso}`, parametros);
  }

  analisis(id: string) {
    return this.cliente.get<Dato>(this.contexto, `${BASE}/analisis/${encodeURIComponent(id)}`, {}, true);
  }
}
