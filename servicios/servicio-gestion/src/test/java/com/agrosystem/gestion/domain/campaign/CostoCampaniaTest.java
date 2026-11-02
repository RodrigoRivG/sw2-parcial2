package com.agrosystem.gestion.domain.campaign;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class CostoCampaniaTest {

    private static final LocalDate HOY = LocalDate.parse("2026-11-02");
    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");

    private CostoCampania crear(String monto, LocalDate fecha) {
        return CostoCampania.crearManual(
                CategoriaCosto.OTRO, new Dinero(new BigDecimal(monto)), fecha, "  Cosecha  ", HOY, AHORA);
    }

    @ParameterizedTest
    @ValueSource(strings = {"0", "0.00", "-1.50"})
    void montoCeroONegativoSeRechaza(String monto) {
        assertThatThrownBy(() -> crear(monto, HOY))
                .isInstanceOfSatisfying(ExcepcionDominio.class, error ->
                        assertThat(error.getCodigo()).isEqualTo("MONTO_INVALIDO"));
    }

    @Test
    void fechaFuturaSeRechaza() {
        assertThatThrownBy(() -> crear("10", HOY.plusDays(1)))
                .isInstanceOfSatisfying(ExcepcionDominio.class, error ->
                        assertThat(error.getCodigo()).isEqualTo("FECHA_COSTO_INVALIDA"));
    }

    @Test
    void creaUnCostoManualConHoyComoFechaValida() {
        CostoCampania costo = crear("10", HOY);

        assertThat(costo.getId()).isNotNull();
        assertThat(costo.getOrigen()).isEqualTo(OrigenCosto.MANUAL);
        assertThat(costo.esManual()).isTrue();
        assertThat(costo.getDescripcion()).isEqualTo("Cosecha");
        assertThat(costo.getMonto().valor()).isEqualByComparingTo("10").hasScaleOf(2);
        assertThat(costo.getFechaRegistro()).isEqualTo(AHORA);
        assertThat(costo.isAnulado()).isFalse();
        assertThat(costo.getIdSaga()).isNull();
        assertThat(costo.getIdLabor()).isNull();
    }

    @Test
    void modificarValidaLasMismasReglas() {
        CostoCampania costo = crear("10", HOY);

        assertThatThrownBy(() -> costo.modificar(
                CategoriaCosto.OTRO, new Dinero(BigDecimal.ZERO), HOY, "x", HOY))
                .isInstanceOf(ExcepcionDominio.class);

        costo.modificar(CategoriaCosto.MAQUINARIA, new Dinero(new BigDecimal("20")), HOY.minusDays(1), " y ", HOY);

        assertThat(costo.getCategoria()).isEqualTo(CategoriaCosto.MAQUINARIA);
        assertThat(costo.getMonto().valor()).isEqualByComparingTo("20");
        assertThat(costo.getFecha()).isEqualTo(HOY.minusDays(1));
        assertThat(costo.getDescripcion()).isEqualTo("y");
    }
}
