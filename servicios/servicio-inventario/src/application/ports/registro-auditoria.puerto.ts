export type AccionAuditoria =
  | 'CREAR'
  | 'MODIFICAR'
  | 'REGISTRAR_MOVIMIENTO'
  | 'DESCONTAR_INSUMOS_SAGA'
  | 'RESTAURAR_INSUMOS_SAGA';

export interface EntradaAuditoria {
  /** `sub` del token en REST; `origen` del mensaje en la Saga. */
  actor: string;
  accion: AccionAuditoria;
  entidad: string;
  idEntidad: string;
}

/** Se guarda dentro de la transacción del cambio que audita. */
export interface RegistroAuditoria {
  registrar(entrada: EntradaAuditoria): Promise<void>;
}
