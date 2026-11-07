import { cargador, type Dato } from './cargador';
import type { ClienteGateway, ContextoLlamada, Parametros } from './cliente-gateway';

const BASE = '/api/gestion/v1';

/** Lecturas de servicio-gestion (rol `lectura_gestion` de la cuenta de servicio). */
export class FuenteGestion {
  readonly parcela;
  readonly cultivo;
  readonly campania;
  readonly indicadores;
  readonly costos;
  readonly produccion;

  constructor(
    private readonly cliente: ClienteGateway,
    private readonly contexto: ContextoLlamada,
  ) {
    // El ID se codifica: un "../" no debe llevar la llamada a otro endpoint del gateway.
    const porId = (ruta: string, id: string, resto = '', parametros = {}) =>
      this.cliente.get<Dato>(this.contexto, `${BASE}/${ruta}/${encodeURIComponent(id)}${resto}`, parametros, true);
    this.parcela = cargador((id) => porId('parcelas', id));
    this.cultivo = cargador((id) => porId('cultivos', id));
    this.campania = cargador((id) => porId('campanias', id));
    this.indicadores = cargador((id) => porId('campanias', id, '/indicadores'));
    // Solo se leen costoTotal y subtotalesPorCategoria, que no dependen de la página.
    this.costos = cargador((id) => porId('campanias', id, '/costos', { tamanio: 1 }));
    // 404 PRODUCCION_NO_REGISTRADA: la campaña no tiene producción → null.
    this.produccion = cargador((id) => porId('campanias', id, '/produccion'));
  }

  listar(recurso: 'parcelas' | 'cultivos' | 'campanias' | 'campanias/historicos', parametros: Parametros) {
    return this.cliente.get<Dato>(this.contexto, `${BASE}/${recurso}`, parametros);
  }
}
