import { randomUUID } from 'node:crypto';
import { Model } from 'mongoose';
import {
  EntradaAuditoria,
  RegistroAuditoria,
} from '../../../application/ports/registro-auditoria.puerto';
import { Reloj } from '../../../application/ports/reloj.puerto';
import { idCorrelacionActual } from '../../contexto-correlacion';
import { opcionesSesion } from './contexto-sesion';
import { DocumentoRegistroAuditoria } from './schemas/registro-auditoria.esquema';

export class RegistroAuditoriaMongo implements RegistroAuditoria {
  constructor(
    private readonly modelo: Model<DocumentoRegistroAuditoria>,
    private readonly reloj: Reloj,
  ) {}

  async registrar(entrada: EntradaAuditoria): Promise<void> {
    await this.modelo.insertMany(
      [
        {
          _id: randomUUID(),
          actor: entrada.actor,
          accion: entrada.accion,
          entidad: entrada.entidad,
          id_entidad: entrada.idEntidad,
          id_correlacion: idCorrelacionActual() ?? null,
          fecha: this.reloj.ahora(),
        },
      ],
      opcionesSesion(),
    );
  }
}
