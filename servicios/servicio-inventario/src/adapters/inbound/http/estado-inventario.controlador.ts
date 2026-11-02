import { Controller, Get, Inject, Query } from '@nestjs/common';
import { ApiBearerAuth, ApiOkResponse, ApiTags } from '@nestjs/swagger';
import { ConsultarEstadoInventarioCasoUso } from '../../../application/use-cases/consultar-estado-inventario.caso-uso';
import { Roles } from './auth/decoradores';
import { ApiErrores } from './documentacion-errores';
import {
  ConsultaEstadoInventario,
  EstadoInventarioRespuesta,
  aEstadoInsumo,
} from './dto/estado-inventario.dto';

@ApiTags('estado-inventario')
@ApiBearerAuth()
@Controller('estado-inventario')
export class EstadoInventarioControlador {
  constructor(
    @Inject(ConsultarEstadoInventarioCasoUso)
    private readonly consultarEstado: ConsultarEstadoInventarioCasoUso,
  ) {}

  @Get()
  @Roles('administrador', 'gerencia', 'lectura_inventario')
  @ApiOkResponse({ type: EstadoInventarioRespuesta })
  @ApiErrores([400, 'DATOS_INVALIDOS'], [401, 'NO_AUTENTICADO'], [403, 'SIN_PERMISO'])
  async consultar(@Query() consulta: ConsultaEstadoInventario): Promise<EstadoInventarioRespuesta> {
    const estado = await this.consultarEstado.consultar(
      { categoria: consulta.categoria, soloStockBajo: consulta.soloStockBajo },
      { pagina: consulta.pagina, tamanio: consulta.tamanio },
    );
    return { ...estado, items: estado.items.map(aEstadoInsumo) };
  }
}
