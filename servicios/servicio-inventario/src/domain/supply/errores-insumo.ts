import { ErrorDominio } from '../shared/error-dominio';

export function insumoNoEncontrado(): ErrorDominio {
  return ErrorDominio.noEncontrado('INSUMO_NO_ENCONTRADO', 'El insumo solicitado no existe.');
}

export function nombreInsumoDuplicado(): ErrorDominio {
  return ErrorDominio.conflicto(
    'NOMBRE_INSUMO_DUPLICADO',
    'Ya existe un insumo con ese nombre.',
  );
}

export function conflictoConcurrencia(): ErrorDominio {
  return ErrorDominio.conflicto(
    'CONFLICTO_CONCURRENCIA',
    'El insumo cambió desde que se consultó. Vuelva a cargarlo e intente de nuevo.',
  );
}
