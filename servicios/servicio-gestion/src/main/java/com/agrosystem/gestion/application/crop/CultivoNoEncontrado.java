package com.agrosystem.gestion.application.crop;

import com.agrosystem.gestion.domain.shared.ExcepcionDominio;

final class CultivoNoEncontrado {

    private CultivoNoEncontrado() {
    }

    static ExcepcionDominio excepcion() {
        return new ExcepcionDominio(
                "CULTIVO_NO_ENCONTRADO", "El cultivo no existe.", ExcepcionDominio.Tipo.NO_ENCONTRADO);
    }
}
