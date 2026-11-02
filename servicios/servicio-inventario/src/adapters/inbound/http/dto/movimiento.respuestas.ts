import { ApiProperty } from '@nestjs/swagger';
import { MovimientoInventario } from '../../../../domain/movement/movimiento-inventario.entidad';
import { TipoMovimiento } from '../../../../domain/movement/tipo-movimiento.enum';

export class MovimientoRespuesta {
  @ApiProperty() id!: string;
  @ApiProperty() idInsumo!: string;
  @ApiProperty({ enum: TipoMovimiento }) tipo!: TipoMovimiento;
  @ApiProperty({ example: '80.000' }) cantidad!: string;
  @ApiProperty({ example: '200.000' }) stockResultante!: string;
  @ApiProperty({ example: '4.8500', description: 'BOB, vigente al registrar el movimiento' })
  costoUnitario!: string;
  @ApiProperty() motivo!: string;
  @ApiProperty({ description: 'sub del usuario, o servicio de origen en la Saga' }) actor!: string;
  @ApiProperty({ nullable: true, type: String }) idSaga!: string | null;
  @ApiProperty({ nullable: true, type: String }) idLabor!: string | null;
  @ApiProperty() fecha!: string;
}

export function aRespuesta(movimiento: MovimientoInventario): MovimientoRespuesta {
  return {
    id: movimiento.id,
    idInsumo: movimiento.idInsumo,
    tipo: movimiento.tipo,
    cantidad: movimiento.cantidad.aTexto(),
    stockResultante: movimiento.stockResultante.aTexto(),
    costoUnitario: movimiento.costoUnitario.aTextoCostoUnitario(),
    motivo: movimiento.motivo,
    actor: movimiento.actor,
    idSaga: movimiento.idSaga,
    idLabor: movimiento.idLabor,
    fecha: movimiento.fecha.toISOString(),
  };
}
