export interface EventoDominio {
  /** `<servicio>.<entidad>.<evento>`, por ejemplo `inventario.stock.bajo`. */
  routingKey: string;
  /** Tipo del sobre común, por ejemplo `StockBajo`. */
  tipo: string;
  datos: Record<string, unknown>;
  idCorrelacion?: string;
}

/** Publica en el exchange `eventos`. Resuelve cuando el broker confirma; si no, rechaza. */
export interface PublicadorEventos {
  publicarEvento(evento: EventoDominio): Promise<void>;
}
