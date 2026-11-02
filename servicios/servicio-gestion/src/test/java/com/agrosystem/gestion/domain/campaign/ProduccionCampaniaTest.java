package com.agrosystem.gestion.domain.campaign;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import org.junit.jupiter.api.Test;

class ProduccionCampaniaTest {

    private static final LocalDate INICIO = LocalDate.parse("2026-01-01");
    private static final LocalDate HOY = LocalDate.parse("2026-11-02");
    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");

    private ProduccionCampania crear(String cantidad, LocalDate fecha, String observaciones) {
        return ProduccionCampania.crear(
                new BigDecimal(cantidad), UnidadProduccion.KILOGRAMO, fecha, observaciones, INICIO, HOY, "usuario-1", AHORA);
    }

    private void esperarError(Runnable accion, String codigo) {
        assertThatThrownBy(accion::run)
                .isInstanceOfSatisfying(ExcepcionDominio.class, error ->
                        assertThat(error.getCodigo()).isEqualTo(codigo));
    }

    @Test
    void cantidadNegativaSeRechaza() {
        esperarError(() -> crear("-0.01", HOY, null), "PRODUCCION_INVALIDA");
    }

    @Test
    void cantidadCeroSeAcepta() {
        assertThat(crear("0", HOY, null).cantidad()).isEqualTo(new BigDecimal("0.00"));
    }

    @Test
    void fechaFueraDeRangoSeRechaza() {
        esperarError(() -> crear("1", INICIO.minusDays(1), null), "FECHA_COSECHA_INVALIDA");
        esperarError(() -> crear("1", HOY.plusDays(1), null), "FECHA_COSECHA_INVALIDA");
    }

    @Test
    void losExtremosDelRangoSonValidos() {
        assertThat(crear("1", INICIO, null).fechaCosecha()).isEqualTo(INICIO);
        assertThat(crear("1", HOY, null).fechaCosecha()).isEqualTo(HOY);
    }

    @Test
    void guardaLosDatosYRecortaLasObservaciones() {
        ProduccionCampania produccion = crear("76500", HOY, "  Peso de balanza  ");

        assertThat(produccion.cantidad()).isEqualTo(new BigDecimal("76500.00"));
        assertThat(produccion.unidad()).isEqualTo(UnidadProduccion.KILOGRAMO);
        assertThat(produccion.observaciones()).isEqualTo("Peso de balanza");
        assertThat(produccion.usuarioRegistro()).isEqualTo("usuario-1");
        assertThat(produccion.fechaRegistro()).isEqualTo(AHORA);
        assertThat(crear("1", HOY, "   ").observaciones()).isNull();
    }
}
