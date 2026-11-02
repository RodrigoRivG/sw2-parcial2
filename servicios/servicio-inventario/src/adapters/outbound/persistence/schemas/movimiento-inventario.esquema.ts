import { Schema, Types } from 'mongoose';

export interface DocumentoMovimiento {
  _id: string;
  id_insumo: string;
  tipo: string;
  cantidad: Types.Decimal128;
  stock_resultante: Types.Decimal128;
  costo_unitario: Types.Decimal128;
  motivo: string;
  actor: string;
  /** Solo en los movimientos de la Saga. */
  id_saga?: string;
  id_labor?: string;
  fecha: Date;
}

export const esquemaMovimiento = new Schema<DocumentoMovimiento>(
  {
    _id: { type: String, required: true },
    id_insumo: { type: String, required: true },
    tipo: { type: String, required: true },
    cantidad: { type: Schema.Types.Decimal128, required: true },
    stock_resultante: { type: Schema.Types.Decimal128, required: true },
    costo_unitario: { type: Schema.Types.Decimal128, required: true },
    motivo: { type: String, required: true },
    actor: { type: String, required: true },
    id_saga: { type: String },
    id_labor: { type: String },
    fecha: { type: Date, required: true },
  },
  { collection: 'movimientos_inventario', versionKey: false },
);
