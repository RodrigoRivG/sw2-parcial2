import {
  Body,
  Controller,
  Get,
  HttpCode,
  Inject,
  Param,
  ParseUUIDPipe,
  Post,
  Put,
  Query,
  Res,
} from '@nestjs/common';
import {
  ApiBearerAuth,
  ApiCreatedResponse,
  ApiExtraModels,
  ApiOkResponse,
  ApiTags,
} from '@nestjs/swagger';
import { Response } from 'express';
import { ActualizarInsumoCasoUso } from '../../../application/use-cases/actualizar-insumo.caso-uso';
import { ConsultarInsumosCasoUso } from '../../../application/use-cases/consultar-insumos.caso-uso';
import { CrearInsumoCasoUso } from '../../../application/use-cases/crear-insumo.caso-uso';
import { Insumo } from '../../../domain/supply/insumo.entidad';
import { Rol, Roles, UsuarioActual, UsuarioAutenticado } from './auth/decoradores';
import { PREFIJO_API } from './configurar-aplicacion';
import { ApiErrores } from './documentacion-errores';
import { PaginaRespuesta } from './dto/consulta-paginada';
import {
  InsumoReducidoRespuesta,
  InsumoRespuesta,
  aRespuesta,
  aRespuestaReducida,
} from './dto/insumo.respuestas';
import {
  ActualizarInsumoSolicitud,
  ConsultaInsumos,
  CrearInsumoSolicitud,
} from './dto/insumo.solicitudes';

const ROLES_VISTA_COMPLETA: Rol[] = ['administrador', 'gerencia', 'lectura_inventario'];
const ROLES_LECTURA: Rol[] = [...ROLES_VISTA_COMPLETA, 'tecnico_campo'];

@ApiTags('insumos')
@ApiBearerAuth()
@ApiExtraModels(InsumoRespuesta, InsumoReducidoRespuesta)
@ApiErrores([401, 'NO_AUTENTICADO'], [403, 'SIN_PERMISO'])
@Controller('insumos')
export class InsumosControlador {
  constructor(
    @Inject(CrearInsumoCasoUso) private readonly crearInsumo: CrearInsumoCasoUso,
    @Inject(ActualizarInsumoCasoUso) private readonly actualizarInsumo: ActualizarInsumoCasoUso,
    @Inject(ConsultarInsumosCasoUso) private readonly consultarInsumos: ConsultarInsumosCasoUso,
  ) {}

  @Post()
  @HttpCode(201)
  @Roles('administrador')
  @ApiCreatedResponse({ type: InsumoRespuesta })
  @ApiErrores(
    [400, 'DATOS_INVALIDOS'],
    [409, 'NOMBRE_INSUMO_DUPLICADO'],
    [422, 'CANTIDAD_INVALIDA, NIVEL_MINIMO_INVALIDO o COSTO_UNITARIO_INVALIDO'],
  )
  async crear(
    @Body() cuerpo: CrearInsumoSolicitud,
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Res({ passthrough: true }) respuesta: Response,
  ): Promise<InsumoRespuesta> {
    const insumo = await this.crearInsumo.ejecutar(cuerpo, usuario.sub);
    respuesta.setHeader('Location', `/${PREFIJO_API}/insumos/${insumo.id}`);
    return aRespuesta(insumo);
  }

  @Get()
  @Roles(...ROLES_LECTURA)
  @ApiOkResponse({
    description:
      'Página de insumos. Vista completa (InsumoRespuesta) o reducida para tecnico_campo (InsumoReducidoRespuesta).',
  })
  @ApiErrores([400, 'DATOS_INVALIDOS'])
  async listar(
    @Query() consulta: ConsultaInsumos,
    @UsuarioActual() usuario: UsuarioAutenticado,
  ): Promise<PaginaRespuesta<InsumoRespuesta | InsumoReducidoRespuesta>> {
    const pagina = await this.consultarInsumos.listar(
      { nombre: consulta.nombre, categoria: consulta.categoria, soloConStock: consulta.soloConStock },
      { pagina: consulta.pagina, tamanio: consulta.tamanio },
    );
    const vista = elegirVista(usuario);
    return { ...pagina, items: pagina.items.map(vista) };
  }

  @Get(':id')
  @Roles(...ROLES_LECTURA)
  @ApiOkResponse({ description: 'InsumoRespuesta, o InsumoReducidoRespuesta para tecnico_campo' })
  @ApiErrores([400, 'DATOS_INVALIDOS'], [404, 'INSUMO_NO_ENCONTRADO'])
  async obtener(
    @Param('id', ParseUUIDPipe) id: string,
    @UsuarioActual() usuario: UsuarioAutenticado,
  ): Promise<InsumoRespuesta | InsumoReducidoRespuesta> {
    return elegirVista(usuario)(await this.consultarInsumos.obtener(id));
  }

  @Put(':id')
  @Roles('administrador')
  @ApiOkResponse({ type: InsumoRespuesta })
  @ApiErrores(
    [400, 'DATOS_INVALIDOS'],
    [404, 'INSUMO_NO_ENCONTRADO'],
    [409, 'NOMBRE_INSUMO_DUPLICADO o CONFLICTO_CONCURRENCIA'],
    [422, 'CANTIDAD_INVALIDA, NIVEL_MINIMO_INVALIDO, COSTO_UNITARIO_INVALIDO o UNIDAD_NO_MODIFICABLE'],
  )
  async actualizar(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() cuerpo: ActualizarInsumoSolicitud,
    @UsuarioActual() usuario: UsuarioAutenticado,
  ): Promise<InsumoRespuesta> {
    return aRespuesta(await this.actualizarInsumo.ejecutar(id, cuerpo, usuario.sub));
  }
}

/** Vista completa si el usuario tiene algún rol de gestión o de integración; si no, la reducida. */
function elegirVista(
  usuario: UsuarioAutenticado,
): (insumo: Insumo) => InsumoRespuesta | InsumoReducidoRespuesta {
  const completa = usuario.roles.some((rol) => (ROLES_VISTA_COMPLETA as string[]).includes(rol));
  return completa ? aRespuesta : aRespuestaReducida;
}
