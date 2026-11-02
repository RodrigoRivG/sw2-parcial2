import { Schema } from 'mongoose';

export interface DocumentoRegistroAuditoria {
  _id: string;
  actor: string;
  accion: string;
  entidad: string;
  id_entidad: string;
  id_correlacion: string | null;
  fecha: Date;
}

export const esquemaRegistroAuditoria = new Schema<DocumentoRegistroAuditoria>(
  {
    _id: { type: String, required: true },
    actor: { type: String, required: true },
    accion: { type: String, required: true },
    entidad: { type: String, required: true },
    id_entidad: { type: String, required: true },
    id_correlacion: { type: String, default: null },
    fecha: { type: Date, required: true },
  },
  { collection: 'registros_auditoria', versionKey: false },
);
