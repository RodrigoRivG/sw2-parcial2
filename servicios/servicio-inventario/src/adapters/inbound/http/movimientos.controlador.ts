import {
  Body,
  Controller,
  Get,
  HttpCode,
  Inject,
  Param,
  ParseUUIDPipe,
  Post,
  Query,
  Res,
} from '@nestjs/common';
import { ApiBearerAuth, ApiCreatedResponse, ApiOkResponse, ApiTags } from '@nestjs/swagger';
import { Response } from 'express';
import { ConsultarMovimientosCasoUso } from '../../../application/use-cases/consultar-movimientos.caso-uso';
import { RegistrarMovimientoCasoUso } from '../../../application/use-cases/registrar-movimiento.caso-uso';
import { Roles, UsuarioActual, UsuarioAutenticado } from './auth/decoradores';
import { PREFIJO_API } from './configurar-aplicacion';
import { ApiErrores } from './documentacion-errores';
import { PaginaRespuesta } from './dto/consulta-paginada';
import { MovimientoRespuesta, aRespuesta } from './dto/movimiento.respuestas';
import { ConsultaMovimientos, RegistrarMovimientoSolicitud } from './dto/movimiento.solicitudes';
import { ErrorValidacion } from './filtro-excepciones-http';

@ApiTags('movimientos')
@ApiBearerAuth()
@ApiErrores([401, 'NO_AUTENTICADO'], [403, 'SIN_PERMISO'])
@Controller('movimientos')
export class MovimientosControlador {
  constructor(
    @Inject(RegistrarMovimientoCasoUso)
    private readonly registrarMovimiento: RegistrarMovimientoCasoUso,
    @Inject(ConsultarMovimientosCasoUso)
    private readonly consultarMovimientos: ConsultarMovimientosCasoUso,
  ) {}

  @Post()
  @HttpCode(201)
  @Roles('administrador')
  @ApiCreatedResponse({ type: MovimientoRespuesta })
  @ApiErrores(
    [400, 'DATOS_INVALIDOS'],
    [404, 'INSUMO_NO_ENCONTRADO'],
    [
      422,
      'CANTIDAD_INVALIDA o STOCK_INSUFICIENTE (detalles: [{ idInsumo, stockDisponible, cantidadSolicitada }])',
    ],
  )
  async registrar(
    @Body() cuerpo: RegistrarMovimientoSolicitud,
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Res({ passthrough: true }) respuesta: Response,
  ): Promise<MovimientoRespuesta> {
    const movimiento = await this.registrarMovimiento.ejecutar(cuerpo, usuario.sub);
    respuesta.setHeader('Location', `/${PREFIJO_API}/movimientos/${movimiento.id}`);
    return aRespuesta(movimiento);
  }

  @Get()
  @Roles('administrador', 'gerencia')
  @ApiOkResponse({ description: 'Página de MovimientoRespuesta, por fecha descendente' })
  @ApiErrores([400, 'DATOS_INVALIDOS'])
  async listar(
    @Query() consulta: ConsultaMovimientos,
  ): Promise<PaginaRespuesta<MovimientoRespuesta>> {
    const desde = consulta.desde ? new Date(consulta.desde) : undefined;
    const hasta = consulta.hasta ? new Date(consulta.hasta) : undefined;
    if (desde && hasta && desde > hasta) {
      throw new ErrorValidacion([
        { campo: 'desde', mensajes: ['desde no puede ser posterior a hasta'] },
      ]);
    }
    const pagina = await this.consultarMovimientos.listar(
      { idInsumo: consulta.idInsumo, tipo: consulta.tipo, idSaga: consulta.idSaga, desde, hasta },
      { pagina: consulta.pagina, tamanio: consulta.tamanio },
    );
    return { ...pagina, items: pagina.items.map(aRespuesta) };
  }

  @Get(':id')
  @Roles('administrador', 'gerencia')
  @ApiOkResponse({ type: MovimientoRespuesta })
  @ApiErrores([400, 'DATOS_INVALIDOS'], [404, 'MOVIMIENTO_NO_ENCONTRADO'])
  async obtener(@Param('id', ParseUUIDPipe) id: string): Promise<MovimientoRespuesta> {
    return aRespuesta(await this.consultarMovimientos.obtener(id));
  }
}
