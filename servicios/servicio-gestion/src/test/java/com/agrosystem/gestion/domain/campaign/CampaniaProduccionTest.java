package com.agrosystem.gestion.domain.campaign;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class CampaniaProduccionTest {

    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");
    private static final LocalDate INICIO = LocalDate.parse("2026-01-01");
    private static final LocalDate HOY = LocalDate.parse("2026-11-02");

    private Campania campania(EstadoCampania estado) {
        return Campania.reconstruir(
                UUID.randomUUID(),
                "Soya",
                UUID.randomUUID(),
                UUID.randomUUID(),
                INICIO,
                LocalDate.parse("2027-03-30"),
                new Hectareas(new BigDecimal("25.5")),
                estado,
                null,
                null,
                1L,
                AHORA.minusSeconds(60),
                AHORA.minusSeconds(60),
                List.of(),
                null);
    }

    private ProduccionCampania registrar(Campania campania, String cantidad) {
        return campania.registrarProduccion(
                new BigDecimal(cantidad), UnidadProduccion.KILOGRAMO, HOY, null, HOY, "usuario-1", AHORA);
    }

    private void esperarError(Runnable accion, String codigo) {
        assertThatThrownBy(accion::run)
                .isInstanceOfSatisfying(ExcepcionDominio.class, error ->
                        assertThat(error.getCodigo()).isEqualTo(codigo));
    }

    @Test
    void soloSeRegistraEnCurso() {
        Campania campania = campania(EstadoCampania.EN_CURSO);

        ProduccionCampania produccion = registrar(campania, "100");

        assertThat(campania.tieneProduccion()).isTrue();
        assertThat(campania.getProduccion()).isEqualTo(produccion);
        assertThat(campania.getFechaActualizacion()).isEqualTo(AHORA);
    }

    @Test
    void enPlanificadaYFinalizadaSeRechaza() {
        Campania planificada = campania(EstadoCampania.PLANIFICADA);
        Campania finalizada = campania(EstadoCampania.FINALIZADA);

        esperarError(() -> registrar(planificada, "100"), "CAMPANIA_NO_EN_CURSO");
        esperarError(() -> registrar(finalizada, "100"), "CAMPANIA_FINALIZADA");
        assertThat(planificada.tieneProduccion()).isFalse();
        assertThat(finalizada.tieneProduccion()).isFalse();
    }

    @Test
    void registrarDeNuevoReemplazaLaAnterior() {
        Campania campania = campania(EstadoCampania.EN_CURSO);
        registrar(campania, "100");

        registrar(campania, "120");

        assertThat(campania.getProduccion().cantidad()).isEqualByComparingTo("120");
    }

    @Test
    void conProduccionSePuedeFinalizarYGuardaLaFecha() {
        Campania campania = campania(EstadoCampania.EN_CURSO);
        registrar(campania, "0");

        campania.cambiarEstado(EstadoCampania.FINALIZADA, AHORA);

        assertThat(campania.getEstado()).isEqualTo(EstadoCampania.FINALIZADA);
        assertThat(campania.getFechaFinalizacion()).isEqualTo(AHORA);
    }

    @Test
    void sinProduccionNoSePuedeFinalizar() {
        Campania campania = campania(EstadoCampania.EN_CURSO);

        esperarError(() -> campania.cambiarEstado(EstadoCampania.FINALIZADA, AHORA), "FINALIZACION_SIN_PRODUCCION");
    }

    @Test
    void despuesDeFinalizarNoCambiaLaProduccion() {
        Campania campania = campania(EstadoCampania.EN_CURSO);
        registrar(campania, "100");
        campania.cambiarEstado(EstadoCampania.FINALIZADA, AHORA);

        esperarError(() -> registrar(campania, "200"), "CAMPANIA_FINALIZADA");

        assertThat(campania.getProduccion().cantidad()).isEqualByComparingTo("100");
    }
}
