package com.agrosystem.gestion.domain.plot;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.math.BigDecimal;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class ParcelaTest {

    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");
    private static final Hectareas SUPERFICIE = new Hectareas(new BigDecimal("25.5"));

    @Test
    void alCrearRecortaTextosYNaceSinVersion() {
        Parcela parcela = Parcela.crear("  Lote Norte  ", SUPERFICIE, "  Km 12 ", "   ", AHORA);

        assertThat(parcela.getId()).isNotNull();
        assertThat(parcela.getNombre()).isEqualTo("Lote Norte");
        assertThat(parcela.getUbicacion()).isEqualTo("Km 12");
        assertThat(parcela.getDescripcion()).isNull();
        assertThat(parcela.getVersion()).isNull();
        assertThat(parcela.getFechaCreacion()).isEqualTo(AHORA);
        assertThat(parcela.getFechaActualizacion()).isEqualTo(AHORA);
    }

    @Test
    void actualizarCambiaLosDatosYConservaIdentidad() {
        Parcela parcela = Parcela.crear("Lote Norte", SUPERFICIE, null, null, AHORA);
        Instant despues = AHORA.plusSeconds(60);

        parcela.actualizar("  Lote Sur ", new Hectareas(new BigDecimal("27")), "Km 20", "Arcilloso", despues);

        assertThat(parcela.getNombre()).isEqualTo("Lote Sur");
        assertThat(parcela.getSuperficie().valor()).isEqualByComparingTo("27");
        assertThat(parcela.getUbicacion()).isEqualTo("Km 20");
        assertThat(parcela.getDescripcion()).isEqualTo("Arcilloso");
        assertThat(parcela.getFechaCreacion()).isEqualTo(AHORA);
        assertThat(parcela.getFechaActualizacion()).isEqualTo(despues);
    }

    @Test
    void laSuperficieInvalidaNoLlegaALaParcela() {
        assertThatThrownBy(() -> Parcela.crear("Lote", new Hectareas(BigDecimal.ZERO), null, null, AHORA))
                .isInstanceOf(ExcepcionDominio.class);
    }
}
