package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.shared.ExcepcionDominio;

final class ErroresCampania {

    private ErroresCampania() {
    }

    static ExcepcionDominio noEncontrada() {
        return new ExcepcionDominio(
                "CAMPANIA_NO_ENCONTRADA", "La campaña no existe.", ExcepcionDominio.Tipo.NO_ENCONTRADO);
    }

    static ExcepcionDominio conflictoVersion() {
        return new ExcepcionDominio(
                "CONFLICTO_CONCURRENCIA",
                "La campaña cambió desde que se leyó. Vuelva a consultarla.",
                ExcepcionDominio.Tipo.CONFLICTO);
    }

    static ExcepcionDominio parcelaConCampaniaEnCurso() {
        return new ExcepcionDominio(
                "PARCELA_CON_CAMPANIA_EN_CURSO",
                "La parcela ya tiene otra campaña en curso.",
                ExcepcionDominio.Tipo.CONFLICTO);
    }

    static ExcepcionDominio sinPermiso() {
        return new ExcepcionDominio(
                "SIN_PERMISO", "No tiene permiso para realizar esta operación.", ExcepcionDominio.Tipo.PROHIBIDO);
    }
}
