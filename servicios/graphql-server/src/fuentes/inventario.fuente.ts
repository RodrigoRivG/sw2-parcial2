import { cargador, type Dato } from './cargador';
import type { ClienteGateway, ContextoLlamada, Parametros } from './cliente-gateway';

const BASE = '/api/inventario/v1';

/** Lecturas de servicio-inventario (rol `lectura_inventario`, vista completa del insumo). */
export class FuenteInventario {
  readonly insumo;

  constructor(
    private readonly cliente: ClienteGateway,
    private readonly contexto: ContextoLlamada,
  ) {
    this.insumo = cargador((id) => this.cliente.get<Dato>(this.contexto, `${BASE}/insumos/${encodeURIComponent(id)}`, {}, true));
  }

  listar(recurso: 'insumos' | 'estado-inventario', parametros: Parametros) {
    return this.cliente.get<Dato>(this.contexto, `${BASE}/${recurso}`, parametros);
  }
}
