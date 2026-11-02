package com.agrosystem.gestion.domain.campaign;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class CampaniaTest {

    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");
    private static final Hectareas SUPERFICIE = new Hectareas(new BigDecimal("25.5"));
    private static final LocalDate INICIO = LocalDate.parse("2026-11-15");
    private static final LocalDate FIN = LocalDate.parse("2027-03-30");
    private static final UUID PARCELA = UUID.randomUUID();
    private static final UUID CULTIVO = UUID.randomUUID();

    private Campania enEstado(EstadoCampania estado) {
        return Campania.reconstruir(
                UUID.randomUUID(), "Soya", PARCELA, CULTIVO, INICIO, FIN, SUPERFICIE,
                estado, null, null, 1L, AHORA, AHORA, List.of());
    }

    private void esperarError(Runnable accion, String codigo) {
        assertThatThrownBy(accion::run)
                .isInstanceOfSatisfying(ExcepcionDominio.class, error -> {
                    assertThat(error.getCodigo()).isEqualTo(codigo);
                    assertThat(error.getTipo()).isEqualTo(ExcepcionDominio.Tipo.REGLA_NEGOCIO);
                });
    }

    @Test
    void naceEnPlanificadaConLaSuperficieRecibida() {
        Campania campania = Campania.crear("  Soya verano  ", PARCELA, CULTIVO, INICIO, FIN, SUPERFICIE, AHORA);

        assertThat(campania.getId()).isNotNull();
        assertThat(campania.getNombre()).isEqualTo("Soya verano");
        assertThat(campania.getEstado()).isEqualTo(EstadoCampania.PLANIFICADA);
        assertThat(campania.getSuperficie()).isEqualTo(SUPERFICIE);
        assertThat(campania.getVersion()).isNull();
        assertThat(campania.getFechaInicioEjecucion()).isNull();
        assertThat(campania.getFechaFinalizacion()).isNull();
    }

    @ParameterizedTest
    @CsvSource({"2027-03-30, 2027-03-30", "2027-03-30, 2027-03-29"})
    void finIgualOAnteriorAlInicioSeRechaza(LocalDate inicio, LocalDate fin) {
        esperarError(
                () -> Campania.crear("Soya", PARCELA, CULTIVO, inicio, fin, SUPERFICIE, AHORA),
                "FECHAS_INVALIDAS");
    }

    @Test
    void pasarAEnCursoGuardaLaFechaDeEjecucion() {
        Campania campania = enEstado(EstadoCampania.PLANIFICADA);

        campania.cambiarEstado(EstadoCampania.EN_CURSO, AHORA);

        assertThat(campania.getEstado()).isEqualTo(EstadoCampania.EN_CURSO);
        assertThat(campania.getFechaInicioEjecucion()).isEqualTo(AHORA);
        assertThat(campania.getFechaActualizacion()).isEqualTo(AHORA);
    }

    @ParameterizedTest
    @CsvSource({
            "PLANIFICADA, PLANIFICADA",
            "PLANIFICADA, FINALIZADA",
            "EN_CURSO, PLANIFICADA",
            "EN_CURSO, EN_CURSO",
            "FINALIZADA, PLANIFICADA",
            "FINALIZADA, EN_CURSO",
            "FINALIZADA, FINALIZADA"
    })
    void transicionesInvalidasSeRechazanSinCambiarElEstado(EstadoCampania origen, EstadoCampania destino) {
        Campania campania = enEstado(origen);

        esperarError(() -> campania.cambiarEstado(destino, AHORA), "TRANSICION_ESTADO_INVALIDA");

        assertThat(campania.getEstado()).isEqualTo(origen);
    }

    @Test
    void finalizarSinProduccionSeRechaza() {
        Campania campania = enEstado(EstadoCampania.EN_CURSO);

        esperarError(() -> campania.cambiarEstado(EstadoCampania.FINALIZADA, AHORA), "FINALIZACION_SIN_PRODUCCION");

        assertThat(campania.getEstado()).isEqualTo(EstadoCampania.EN_CURSO);
        assertThat(campania.getFechaFinalizacion()).isNull();
    }

    @Test
    void enPlanificadaSeModificaTodo() {
        Campania campania = enEstado(EstadoCampania.PLANIFICADA);
        UUID otraParcela = UUID.randomUUID();
        UUID otroCultivo = UUID.randomUUID();
        Hectareas otraSuperficie = new Hectareas(new BigDecimal("10"));

        campania.actualizarDatos(" Otra ", otraParcela, otroCultivo, INICIO.plusDays(1), FIN.plusDays(1), otraSuperficie, AHORA);

        assertThat(campania.getNombre()).isEqualTo("Otra");
        assertThat(campania.getIdParcela()).isEqualTo(otraParcela);
        assertThat(campania.getIdCultivo()).isEqualTo(otroCultivo);
        assertThat(campania.getFechaInicio()).isEqualTo(INICIO.plusDays(1));
        assertThat(campania.getFechaFin()).isEqualTo(FIN.plusDays(1));
        assertThat(campania.getSuperficie()).isEqualTo(otraSuperficie);
    }

    @Test
    void enCursoSoloSeModificanNombreYFechaDeFin() {
        Campania campania = enEstado(EstadoCampania.EN_CURSO);

        campania.actualizarDatos("Otra", PARCELA, CULTIVO, INICIO, FIN.plusDays(5), SUPERFICIE, AHORA);

        assertThat(campania.getNombre()).isEqualTo("Otra");
        assertThat(campania.getFechaFin()).isEqualTo(FIN.plusDays(5));
    }

    @Test
    void enCursoNoSeModificanParcelaCultivoNiFechaDeInicio() {
        Campania campania = enEstado(EstadoCampania.EN_CURSO);

        esperarError(() -> campania.actualizarDatos("S", UUID.randomUUID(), CULTIVO, INICIO, FIN, SUPERFICIE, AHORA),
                "CAMPO_NO_MODIFICABLE");
        esperarError(() -> campania.actualizarDatos("S", PARCELA, UUID.randomUUID(), INICIO, FIN, SUPERFICIE, AHORA),
                "CAMPO_NO_MODIFICABLE");
        esperarError(() -> campania.actualizarDatos("S", PARCELA, CULTIVO, INICIO.plusDays(1), FIN, SUPERFICIE, AHORA),
                "CAMPO_NO_MODIFICABLE");
    }

    @Test
    void finalizadaNoAdmiteModificaciones() {
        Campania campania = enEstado(EstadoCampania.FINALIZADA);

        esperarError(() -> campania.actualizarDatos("Otra", PARCELA, CULTIVO, INICIO, FIN, SUPERFICIE, AHORA),
                "CAMPANIA_FINALIZADA");
        assertThat(campania.getNombre()).isEqualTo("Soya");
    }

    @Test
    void modificarConFechasInvalidasSeRechaza() {
        Campania campania = enEstado(EstadoCampania.EN_CURSO);

        esperarError(() -> campania.actualizarDatos("S", PARCELA, CULTIVO, INICIO, INICIO, SUPERFICIE, AHORA),
                "FECHAS_INVALIDAS");
    }
}
