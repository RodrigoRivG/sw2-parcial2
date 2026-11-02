package com.agrosystem.gestion.domain.shared;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class ExcepcionDominioTest {

    @Test
    void conservaCodigoMensajeYTipo() {
        ExcepcionDominio error = new ExcepcionDominio("CODIGO", "Mensaje.", ExcepcionDominio.Tipo.CONFLICTO);

        assertThat(error.getCodigo()).isEqualTo("CODIGO");
        assertThat(error.getMessage()).isEqualTo("Mensaje.");
        assertThat(error.getTipo()).isEqualTo(ExcepcionDominio.Tipo.CONFLICTO);
    }
}
