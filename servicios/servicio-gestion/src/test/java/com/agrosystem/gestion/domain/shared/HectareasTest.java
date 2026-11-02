package com.agrosystem.gestion.domain.shared;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class HectareasTest {

    @ParameterizedTest
    @ValueSource(strings = {"0", "0.0000", "-1", "-0.0001", "1.00001"})
    void rechazaValoresInvalidos(String valor) {
        assertThatThrownBy(() -> new Hectareas(new BigDecimal(valor)))
                .isInstanceOfSatisfying(ExcepcionDominio.class, error -> {
                    assertThat(error.getCodigo()).isEqualTo("SUPERFICIE_INVALIDA");
                    assertThat(error.getTipo()).isEqualTo(ExcepcionDominio.Tipo.REGLA_NEGOCIO);
                });
    }

    @Test
    void rechazaNulo() {
        assertThatThrownBy(() -> new Hectareas(null)).isInstanceOf(ExcepcionDominio.class);
    }

    @Test
    void aceptaPositivosYFijaCuatroDecimales() {
        assertThat(new Hectareas(new BigDecimal("25.5")).valor()).isEqualByComparingTo("25.5").hasScaleOf(4);
        assertThat(new Hectareas(new BigDecimal("0.0001")).valor()).isEqualByComparingTo("0.0001");
    }
}
