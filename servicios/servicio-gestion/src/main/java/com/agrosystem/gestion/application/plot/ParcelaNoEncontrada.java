package com.agrosystem.gestion.application.plot;

import com.agrosystem.gestion.domain.shared.ExcepcionDominio;

final class ParcelaNoEncontrada {

    private ParcelaNoEncontrada() {
    }

    static ExcepcionDominio excepcion() {
        return new ExcepcionDominio(
                "PARCELA_NO_ENCONTRADA", "La parcela no existe.", ExcepcionDominio.Tipo.NO_ENCONTRADO);
    }
}
