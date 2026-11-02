import { Module } from '@nestjs/common';
import { InventarioModulo } from './modules/inventario.modulo';

@Module({
  imports: [InventarioModulo],
})
export class AppModule {}
