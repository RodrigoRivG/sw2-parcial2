import { Schema, Types } from 'mongoose';

export interface DocumentoInsumo {
  _id: string;
  nombre: string;
  nombre_normalizado: string;
  categoria: string;
  unidad: string;
  stock: Types.Decimal128;
  nivel_minimo: Types.Decimal128;
  costo_unitario: Types.Decimal128;
  descripcion: string | null;
  tiene_movimientos: boolean;
  fecha_ultima_alerta: Date | null;
  reserva_alerta_hasta: Date | null;
  version: number;
  fecha_creacion: Date;
  fecha_actualizacion: Date;
}

export const esquemaInsumo = new Schema<DocumentoInsumo>(
  {
    _id: { type: String, required: true },
    nombre: { type: String, required: true },
    nombre_normalizado: { type: String, required: true },
    categoria: { type: String, required: true },
    unidad: { type: String, required: true },
    stock: { type: Schema.Types.Decimal128, required: true },
    nivel_minimo: { type: Schema.Types.Decimal128, required: true },
    costo_unitario: { type: Schema.Types.Decimal128, required: true },
    descripcion: { type: String, default: null },
    tiene_movimientos: { type: Boolean, required: true },
    fecha_ultima_alerta: { type: Date, default: null },
    reserva_alerta_hasta: { type: Date, default: null },
    version: { type: Number, required: true },
    fecha_creacion: { type: Date, required: true },
    fecha_actualizacion: { type: Date, required: true },
  },
  { collection: 'insumos', versionKey: false },
);
