import type { Dato } from './cargador';
import type { ClienteGateway, ContextoLlamada, Parametros } from './cliente-gateway';

const BASE = '/api/operaciones/v1';

/** Lecturas de servicio-operaciones (rol `lectura_operaciones`). Paginación por cursor, sin `mias`. */
export class FuenteOperaciones {
  constructor(
    private readonly cliente: ClienteGateway,
    private readonly contexto: ContextoLlamada,
  ) {}

  listar(recurso: 'labores' | 'incidencias', parametros: Parametros) {
    return this.cliente.get<Dato>(this.contexto, `${BASE}/${recurso}`, parametros);
  }
}
