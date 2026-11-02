package com.agrosystem.gestion.domain.crop;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class CultivoTest {

    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");

    @Test
    void alCrearRecortaTextos() {
        Cultivo cultivo = Cultivo.crear("  Soya ", " Munasqa ", UnidadProduccion.KILOGRAMO, " Verano ", AHORA);

        assertThat(cultivo.getId()).isNotNull();
        assertThat(cultivo.getNombre()).isEqualTo("Soya");
        assertThat(cultivo.getVariedad()).isEqualTo("Munasqa");
        assertThat(cultivo.getDescripcion()).isEqualTo("Verano");
        assertThat(cultivo.getUnidadMedida()).isEqualTo(UnidadProduccion.KILOGRAMO);
        assertThat(cultivo.getVersion()).isNull();
    }

    @Test
    void variedadVaciaOSoloEspaciosSeGuardaComoNula() {
        assertThat(Cultivo.crear("Soya", "   ", UnidadProduccion.KILOGRAMO, null, AHORA).getVariedad()).isNull();
        assertThat(Cultivo.crear("Soya", "", UnidadProduccion.KILOGRAMO, null, AHORA).getVariedad()).isNull();
    }

    @Test
    void actualizarCambiaLosDatosYConservaLaUnidad() {
        Cultivo cultivo = Cultivo.crear("Soja", "A", UnidadProduccion.KILOGRAMO, "x", AHORA);
        Instant despues = AHORA.plusSeconds(60);

        cultivo.actualizar(" Soya ", "  ", "y", despues);

        assertThat(cultivo.getNombre()).isEqualTo("Soya");
        assertThat(cultivo.getVariedad()).isNull();
        assertThat(cultivo.getDescripcion()).isEqualTo("y");
        assertThat(cultivo.getUnidadMedida()).isEqualTo(UnidadProduccion.KILOGRAMO);
        assertThat(cultivo.getFechaCreacion()).isEqualTo(AHORA);
        assertThat(cultivo.getFechaActualizacion()).isEqualTo(despues);
    }
}
