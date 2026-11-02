import { Controller, Get, Inject, Res } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { Response } from 'express';
import { Connection } from 'mongoose';
import { CONEXION_MONGO } from '../../outbound/persistence/conexion-mongo';
import { Publica } from './auth/decoradores';

type Estado = 'UP' | 'DOWN';

const LIMITE_PING_MS = 2000;

@ApiTags('salud')
@Publica()
@Controller('salud')
export class SaludControlador {
  constructor(@Inject(CONEXION_MONGO) private readonly conexion: Connection) {}

  @Get()
  salud(@Res({ passthrough: true }) respuesta: Response) {
    return this.readiness(respuesta);
  }

  @Get('liveness')
  liveness(): { estado: Estado } {
    return { estado: 'UP' };
  }

  @Get('readiness')
  async readiness(@Res({ passthrough: true }) respuesta: Response) {
    const mongodb = await this.estadoMongo();
    const estado: Estado = mongodb === 'UP' ? 'UP' : 'DOWN';
    respuesta.status(estado === 'UP' ? 200 : 503);
    return { estado, componentes: { mongodb } };
  }

  private async estadoMongo(): Promise<Estado> {
    try {
      const ping = this.conexion.db?.admin().ping();
      if (!ping) {
        return 'DOWN';
      }
      await Promise.race([
        ping,
        new Promise((_, rechazar) =>
          setTimeout(() => rechazar(new Error('Tiempo agotado')), LIMITE_PING_MS).unref(),
        ),
      ]);
      return 'UP';
    } catch {
      return 'DOWN';
    }
  }
}
