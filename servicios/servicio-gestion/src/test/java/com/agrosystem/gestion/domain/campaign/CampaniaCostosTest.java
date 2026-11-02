package com.agrosystem.gestion.domain.campaign;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class CampaniaCostosTest {

    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");
    private static final LocalDate HOY = LocalDate.parse("2026-11-02");

    private Campania campania(EstadoCampania estado, CostoCampania... costos) {
        return Campania.reconstruir(
                UUID.randomUUID(),
                "Soya",
                UUID.randomUUID(),
                UUID.randomUUID(),
                LocalDate.parse("2026-11-15"),
                LocalDate.parse("2027-03-30"),
                new Hectareas(new BigDecimal("25.5")),
                estado,
                null,
                null,
                1L,
                AHORA.minusSeconds(60),
                AHORA.minusSeconds(60),
                new ArrayList<>(List.of(costos)));
    }

    private CostoCampania costoSaga(String monto, boolean anulado) {
        return CostoCampania.reconstruir(
                UUID.randomUUID(), CategoriaCosto.INSUMO, dinero(monto), HOY, "Insumos", OrigenCosto.SAGA,
                UUID.randomUUID(), UUID.randomUUID(), anulado, anulado ? AHORA : null, AHORA);
    }

    private CostoCampania costoManual(CategoriaCosto categoria, String monto) {
        return CostoCampania.crearManual(categoria, dinero(monto), HOY, "Manual", HOY, AHORA);
    }

    private Dinero dinero(String monto) {
        return new Dinero(new BigDecimal(monto));
    }

    private void esperarError(Runnable accion, String codigo) {
        assertThatThrownBy(accion::run)
                .isInstanceOfSatisfying(ExcepcionDominio.class, error ->
                        assertThat(error.getCodigo()).isEqualTo(codigo));
    }

    @ParameterizedTest
    @EnumSource(value = EstadoCampania.class, names = {"PLANIFICADA", "EN_CURSO"})
    void seRegistranCostosEnCampaniasNoFinalizadas(EstadoCampania estado) {
        Campania campania = campania(estado);

        CostoCampania costo = campania.registrarCostoManual(
                CategoriaCosto.MANO_DE_OBRA, dinero("1500"), HOY, "Cosecha", HOY, AHORA);

        assertThat(campania.getCostos()).containsExactly(costo);
        assertThat(campania.getFechaActualizacion()).isEqualTo(AHORA);
    }

    @Test
    void finalizadaRechazaRegistrarModificarYEliminar() {
        CostoCampania manual = costoManual(CategoriaCosto.OTRO, "10");
        CostoCampania saga = costoSaga("20", false);
        Campania campania = campania(EstadoCampania.FINALIZADA, manual, saga);

        esperarError(() -> campania.registrarCostoManual(CategoriaCosto.OTRO, dinero("1"), HOY, "x", HOY, AHORA),
                "CAMPANIA_FINALIZADA");
        esperarError(() -> campania.modificarCostoManual(manual.getId(), CategoriaCosto.OTRO, dinero("1"), HOY, "x", HOY, AHORA),
                "CAMPANIA_FINALIZADA");
        esperarError(() -> campania.eliminarCostoManual(manual.getId(), AHORA), "CAMPANIA_FINALIZADA");
        esperarError(() -> campania.eliminarCostoManual(saga.getId(), AHORA), "CAMPANIA_FINALIZADA");
        assertThat(campania.getCostos()).hasSize(2);
    }

    @Test
    void costosDeLaSagaNoSeModificanNiEliminan() {
        CostoCampania saga = costoSaga("20", false);
        Campania campania = campania(EstadoCampania.EN_CURSO, saga);

        esperarError(() -> campania.modificarCostoManual(saga.getId(), CategoriaCosto.OTRO, dinero("1"), HOY, "x", HOY, AHORA),
                "COSTO_NO_EDITABLE");
        esperarError(() -> campania.eliminarCostoManual(saga.getId(), AHORA), "COSTO_NO_EDITABLE");
        assertThat(saga.getMonto().valor()).isEqualByComparingTo("20");
        assertThat(campania.getCostos()).hasSize(1);
    }

    @Test
    void costoInexistenteLanzaCostoNoEncontrado() {
        Campania campania = campania(EstadoCampania.EN_CURSO);

        esperarError(() -> campania.eliminarCostoManual(UUID.randomUUID(), AHORA), "COSTO_NO_ENCONTRADO");
    }

    @Test
    void modificarYEliminarCostoManual() {
        CostoCampania manual = costoManual(CategoriaCosto.OTRO, "10");
        Campania campania = campania(EstadoCampania.EN_CURSO, manual);

        campania.modificarCostoManual(manual.getId(), CategoriaCosto.MAQUINARIA, dinero("30"), HOY, "y", HOY, AHORA);
        assertThat(campania.costoTotal().valor()).isEqualByComparingTo("30");
        assertThat(campania.getFechaActualizacion()).isEqualTo(AHORA);

        campania.eliminarCostoManual(manual.getId(), AHORA);
        assertThat(campania.getCostos()).isEmpty();
        assertThat(campania.costoTotal().valor()).isEqualByComparingTo("0");
    }

    @Test
    void totalesSonExactosYExcluyenLosAnulados() {
        Campania campania = campania(
                EstadoCampania.EN_CURSO,
                costoManual(CategoriaCosto.MANO_DE_OBRA, "0.10"),
                costoManual(CategoriaCosto.MANO_DE_OBRA, "0.20"),
                costoSaga("820.50", false),
                costoSaga("1000.00", true));

        assertThat(campania.costoTotal().valor()).isEqualTo(new BigDecimal("820.80"));
        assertThat(campania.cantidadCostos()).isEqualTo(3);
        assertThat(campania.subtotalesPorCategoria().get(CategoriaCosto.MANO_DE_OBRA).valor())
                .isEqualTo(new BigDecimal("0.30"));
        assertThat(campania.subtotalesPorCategoria().get(CategoriaCosto.INSUMO).valor())
                .isEqualTo(new BigDecimal("820.50"));
        assertThat(campania.subtotalesPorCategoria().get(CategoriaCosto.OTRO).valor())
                .isEqualTo(new BigDecimal("0.00"));
    }
}
