import { Schema, Types } from 'mongoose';

export interface DocumentoDescuento {
  tipo: 'InsumosDescontados' | 'InsumosRechazados';
  costo_total?: Types.Decimal128;
  items?: { id_insumo: string; cantidad: Types.Decimal128; costo_unitario: Types.Decimal128 }[];
  codigo?: string;
  motivo?: string;
  insumos_afectados?: {
    id_insumo: string;
    cantidad_solicitada: string;
    stock_disponible: string | null;
  }[];
}

export interface DocumentoRestauracion {
  sin_efecto: boolean;
  items: { id_insumo: string; cantidad: Types.Decimal128 }[];
}

export interface DocumentoSagaProcesada {
  _id: string;
  id_labor: string;
  resultado: string | null;
  descuento: DocumentoDescuento | null;
  restauracion: DocumentoRestauracion | null;
  fecha_procesamiento: Date;
  fecha_actualizacion: Date;
}

/**
 * `insumos_afectados` guarda las cantidades como texto: en un rechazo `DATOS_INVALIDOS` pueden no ser
 * decimales válidos, y solo se repiten tal cual en la respuesta.
 */
export const esquemaSagaProcesada = new Schema<DocumentoSagaProcesada>(
  {
    _id: { type: String, required: true },
    id_labor: { type: String, required: true },
    resultado: { type: String, default: null },
    descuento: { type: Schema.Types.Mixed, default: null },
    restauracion: { type: Schema.Types.Mixed, default: null },
    fecha_procesamiento: { type: Date, required: true },
    fecha_actualizacion: { type: Date, required: true },
  },
  { collection: 'sagas_procesadas', versionKey: false, minimize: false },
);
