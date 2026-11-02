package com.agrosystem.gestion.domain.campaign;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class CampaniaCostoSagaTest {

    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");
    private static final LocalDate FECHA = LocalDate.parse("2026-11-02");
    private static final Dinero MONTO = new Dinero(new BigDecimal("820.50"));
    private static final UUID SAGA = UUID.randomUUID();
    private static final UUID LABOR = UUID.randomUUID();

    private Campania campania(EstadoCampania estado) {
        return Campania.reconstruir(
                UUID.randomUUID(), "Soya", UUID.randomUUID(), UUID.randomUUID(),
                LocalDate.parse("2026-01-01"), LocalDate.parse("2027-01-01"),
                new Hectareas(new BigDecimal("25.5")), estado, null, null, 1L,
                AHORA.minusSeconds(60), AHORA.minusSeconds(60), List.of(), null);
    }

    @ParameterizedTest
    @EnumSource(value = EstadoCampania.class, names = {"PLANIFICADA", "EN_CURSO"})
    void registraUnCostoDeInsumosConOrigenSaga(EstadoCampania estado) {
        Campania campania = campania(estado);

        CostoCampania costo = campania.registrarCostoSaga(SAGA, LABOR, MONTO, FECHA, AHORA);

        assertThat(costo.getCategoria()).isEqualTo(CategoriaCosto.INSUMO);
        assertThat(costo.getOrigen()).isEqualTo(OrigenCosto.SAGA);
        assertThat(costo.getIdSaga()).isEqualTo(SAGA);
        assertThat(costo.getIdLabor()).isEqualTo(LABOR);
        assertThat(costo.getFecha()).isEqualTo(FECHA);
        assertThat(costo.getDescripcion()).isEqualTo("Insumos de la labor " + LABOR);
        assertThat(campania.costoTotal().valor()).isEqualByComparingTo("820.50");
        assertThat(campania.getFechaActualizacion()).isEqualTo(AHORA);
    }

    @Test
    void finalizadaRechazaRegistroYAnulacion() {
        Campania campania = campania(EstadoCampania.FINALIZADA);

        assertThatThrownBy(() -> campania.registrarCostoSaga(SAGA, LABOR, MONTO, FECHA, AHORA))
                .isInstanceOfSatisfying(ExcepcionDominio.class, error ->
                        assertThat(error.getCodigo()).isEqualTo("CAMPANIA_FINALIZADA"));
        assertThatThrownBy(() -> campania.anularCostoSaga(SAGA, AHORA))
                .isInstanceOfSatisfying(ExcepcionDominio.class, error ->
                        assertThat(error.getCodigo()).isEqualTo("CAMPANIA_FINALIZADA"));
    }

    @Test
    void montoCeroSeRechaza() {
        assertThatThrownBy(() -> campania(EstadoCampania.EN_CURSO)
                .registrarCostoSaga(SAGA, LABOR, new Dinero(BigDecimal.ZERO), FECHA, AHORA))
                .isInstanceOf(ExcepcionDominio.class);
    }

    @Test
    void anularConservaElCostoPeroDejaDeSumar() {
        Campania campania = campania(EstadoCampania.EN_CURSO);
        CostoCampania costo = campania.registrarCostoSaga(SAGA, LABOR, MONTO, FECHA, AHORA);
        Instant despues = AHORA.plusSeconds(60);

        campania.anularCostoSaga(SAGA, despues);

        assertThat(campania.getCostos()).containsExactly(costo);
        assertThat(costo.isAnulado()).isTrue();
        assertThat(costo.getFechaAnulacion()).isEqualTo(despues);
        assertThat(campania.costoTotal().valor()).isEqualByComparingTo("0");
        assertThat(campania.cantidadCostos()).isZero();
        assertThat(campania.getFechaActualizacion()).isEqualTo(despues);
    }

    @Test
    void sagaSinCostoEnLaCampaniaEsUnErrorInterno() {
        assertThatThrownBy(() -> campania(EstadoCampania.EN_CURSO).anularCostoSaga(UUID.randomUUID(), AHORA))
                .isInstanceOf(IllegalStateException.class);
    }
}
