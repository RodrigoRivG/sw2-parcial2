package com.agrosystem.gestion.domain.campaign;

import static org.assertj.core.api.Assertions.assertThat;

import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.EnumSource;

class IndicadoresCampaniaTest {

    private static final Hectareas SUPERFICIE = new Hectareas(new BigDecimal("25.5"));
    private static final Dinero SIN_COSTOS = Dinero.CERO;

    private Dinero dinero(String valor) {
        return new Dinero(new BigDecimal(valor));
    }

    private IndicadoresCampania calcular(String produccion, Dinero costo) {
        BigDecimal cantidad = produccion == null ? null : new BigDecimal(produccion);
        return IndicadoresCampania.calcular(cantidad, costo, SUPERFICIE, EstadoCampania.EN_CURSO);
    }

    @Test
    void conProduccionYCostosCalculaAmbos() {
        IndicadoresCampania indicadores = calcular("76500.00", dinero("38250.00"));

        assertThat(indicadores.rendimientoPorHectarea()).isEqualTo(new BigDecimal("3000.00"));
        assertThat(indicadores.costoPorHectarea()).isEqualTo(new BigDecimal("1500.00"));
        assertThat(indicadores.costoTotal()).isEqualTo(dinero("38250.00"));
        assertThat(indicadores.motivosNoDisponible()).isEmpty();
    }

    @Test
    void sinProduccionAmbosSonNulosConSuMotivo() {
        IndicadoresCampania indicadores = calcular(null, dinero("38250.00"));

        assertThat(indicadores.rendimientoPorHectarea()).isNull();
        assertThat(indicadores.costoPorHectarea()).isNull();
        assertThat(indicadores.costoTotal()).isEqualTo(dinero("38250.00"));
        assertThat(indicadores.motivosNoDisponible()).containsExactly(MotivoIndicadorNoDisponible.SIN_PRODUCCION);
    }

    @Test
    void sinCostosAmbosSonNulosConSuMotivo() {
        IndicadoresCampania indicadores = calcular("76500.00", SIN_COSTOS);

        assertThat(indicadores.rendimientoPorHectarea()).isNull();
        assertThat(indicadores.costoPorHectarea()).isNull();
        assertThat(indicadores.costoTotal().valor()).isEqualTo(new BigDecimal("0.00"));
        assertThat(indicadores.motivosNoDisponible()).containsExactly(MotivoIndicadorNoDisponible.SIN_COSTOS);
    }

    @Test
    void sinProduccionNiCostosIncluyeAmbosMotivos() {
        IndicadoresCampania indicadores = calcular(null, SIN_COSTOS);

        assertThat(indicadores.rendimientoPorHectarea()).isNull();
        assertThat(indicadores.costoPorHectarea()).isNull();
        assertThat(indicadores.motivosNoDisponible()).containsExactly(
                MotivoIndicadorNoDisponible.SIN_PRODUCCION, MotivoIndicadorNoDisponible.SIN_COSTOS);
    }

    @Test
    void produccionCeroEsUnDatoReal() {
        IndicadoresCampania indicadores = calcular("0.00", dinero("38250.00"));

        assertThat(indicadores.rendimientoPorHectarea()).isEqualTo(new BigDecimal("0.00"));
        assertThat(indicadores.costoPorHectarea()).isEqualTo(new BigDecimal("1500.00"));
        assertThat(indicadores.motivosNoDisponible()).isEmpty();
    }

    @ParameterizedTest
    @CsvSource({
            "100000.00, 30, 3333.33",
            "100.00, 3, 33.33",
            "200.00, 3, 66.67",
            "1.00, 8, 0.13"
    })
    void divisionesConDecimalesRedondeanAlFinalMitadHaciaArriba(String valor, String hectareas, String esperado) {
        IndicadoresCampania indicadores = IndicadoresCampania.calcular(
                new BigDecimal(valor), dinero("1.00"), new Hectareas(new BigDecimal(hectareas)), EstadoCampania.EN_CURSO);

        assertThat(indicadores.rendimientoPorHectarea()).isEqualTo(new BigDecimal(esperado));
    }

    @ParameterizedTest
    @EnumSource(EstadoCampania.class)
    void soloEsDefinitivoSiLaCampaniaEstaFinalizada(EstadoCampania estado) {
        IndicadoresCampania indicadores =
                IndicadoresCampania.calcular(new BigDecimal("1"), dinero("1"), SUPERFICIE, estado);

        assertThat(indicadores.definitivo()).isEqualTo(estado == EstadoCampania.FINALIZADA);
    }

    @Test
    void losCostosAnuladosNoCuentan() {
        Instant ahora = Instant.parse("2026-11-02T14:00:00Z");
        CostoCampania anulado = CostoCampania.reconstruir(
                UUID.randomUUID(), CategoriaCosto.INSUMO, dinero("500"), LocalDate.parse("2026-11-01"), "Insumos",
                OrigenCosto.SAGA, UUID.randomUUID(), UUID.randomUUID(), true, ahora, ahora);
        Campania campania = Campania.reconstruir(
                UUID.randomUUID(), "Soya", UUID.randomUUID(), UUID.randomUUID(),
                LocalDate.parse("2026-01-01"), LocalDate.parse("2027-01-01"), SUPERFICIE,
                EstadoCampania.EN_CURSO, ahora, null, 1L, ahora, ahora, List.of(anulado),
                new ProduccionCampania(new BigDecimal("100.00"), UnidadProduccion.KILOGRAMO,
                        LocalDate.parse("2026-11-01"), null, ahora, "usuario-1"));

        IndicadoresCampania indicadores = IndicadoresCampania.calcular(
                campania.getProduccion().cantidad(), campania.costoTotal(), campania.getSuperficie(), campania.getEstado());

        assertThat(indicadores.costoPorHectarea()).isNull();
        assertThat(indicadores.motivosNoDisponible()).containsExactly(MotivoIndicadorNoDisponible.SIN_COSTOS);
    }
}
