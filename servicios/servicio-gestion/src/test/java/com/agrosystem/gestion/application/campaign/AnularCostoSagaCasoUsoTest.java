package com.agrosystem.gestion.application.campaign;

import static org.assertj.core.api.Assertions.assertThat;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.campaign.CostoCampania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.FiltrosCampania;
import com.agrosystem.gestion.domain.campaign.OrigenCosto;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.saga.RepositorioSagaProcesada;
import com.agrosystem.gestion.domain.saga.ResultadoSagaProcesada;
import com.agrosystem.gestion.domain.saga.SagaProcesada;
import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.Hectareas;
import com.agrosystem.gestion.domain.shared.Pagina;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

/** Cada fila de la tabla de RQ-SAG-06. */
class AnularCostoSagaCasoUsoTest {

    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");
    private static final UUID SAGA = UUID.randomUUID();
    private static final UUID LABOR = UUID.randomUUID();
    private static final UUID COSTO = UUID.randomUUID();
    private static final UUID CAMPANIA = UUID.randomUUID();

    private final CampaniasEnMemoria campanias = new CampaniasEnMemoria();
    private final SagasEnMemoria sagas = new SagasEnMemoria();
    private final AuditoriaEnMemoria auditoria = new AuditoriaEnMemoria();
    private final AnularCostoSagaCasoUso casoUso =
            new AnularCostoSagaCasoUso(campanias, sagas, auditoria, Clock.fixed(AHORA, ZoneOffset.UTC));

    private RespuestaSaga anular() {
        return casoUso.ejecutar(new ComandoAnularCosto(UUID.randomUUID(), SAGA, LABOR, CAMPANIA, "servicio-operaciones"));
    }

    private void prepararRegistrada(EstadoCampania estado) {
        CostoCampania costo = CostoCampania.reconstruir(
                COSTO, CategoriaCosto.INSUMO, new Dinero(new BigDecimal("820.50")), LocalDate.parse("2026-11-01"),
                "Insumos", OrigenCosto.SAGA, SAGA, LABOR, false, null, AHORA);
        campanias.campania = Campania.reconstruir(
                CAMPANIA, "Soya", UUID.randomUUID(), UUID.randomUUID(),
                LocalDate.parse("2026-01-01"), LocalDate.parse("2027-01-01"),
                new Hectareas(new BigDecimal("25.5")), estado, null, null, 1L, AHORA, AHORA, List.of(costo), null);
        sagas.saga = SagaProcesada.registrada(SAGA, CAMPANIA, LABOR, COSTO, new BigDecimal("820.50"), AHORA);
    }

    @Test
    void registradoEnCampaniaNoFinalizadaAnulaElCosto() {
        prepararRegistrada(EstadoCampania.EN_CURSO);

        RespuestaSaga respuesta = anular();

        assertThat(respuesta.tipo()).isEqualTo(RespuestaSaga.ANULADO);
        assertThat(respuesta.datos()).containsEntry("sinEfecto", false).containsEntry("idCosto", COSTO);
        assertThat(sagas.saga.getResultado()).isEqualTo(ResultadoSagaProcesada.ANULADO);
        assertThat(campanias.campania.costoTotal().valor()).isEqualByComparingTo("0");
        assertThat(campanias.guardadas).isEqualTo(1);
        assertThat(auditoria.acciones).containsExactly(AccionAuditoria.ANULAR_COSTO_SAGA);
    }

    @Test
    void registradoEnCampaniaFinalizadaConservaElCosto() {
        prepararRegistrada(EstadoCampania.FINALIZADA);

        RespuestaSaga respuesta = anular();

        assertThat(respuesta.tipo()).isEqualTo(RespuestaSaga.ANULACION_RECHAZADA);
        assertThat(respuesta.datos())
                .containsEntry("codigo", "CAMPANIA_FINALIZADA")
                .containsEntry("idCosto", COSTO);
        assertThat(sagas.saga.getResultado()).isEqualTo(ResultadoSagaProcesada.REGISTRADO);
        assertThat(sagas.saga.getAnulacionResultado()).isEqualTo(SagaProcesada.ANULACION_RECHAZADA);
        assertThat(campanias.campania.costoTotal().valor()).isEqualByComparingTo("820.50");
        assertThat(campanias.guardadas).isZero();
        assertThat(auditoria.acciones).isEmpty();
    }

    @Test
    void sinProcesarGuardaAnuladoSinEfecto() {
        RespuestaSaga respuesta = anular();

        assertThat(respuesta.tipo()).isEqualTo(RespuestaSaga.ANULADO);
        assertThat(respuesta.datos()).containsEntry("sinEfecto", true).containsEntry("idCosto", null);
        assertThat(sagas.saga.getResultado()).isEqualTo(ResultadoSagaProcesada.ANULADO);
        assertThat(auditoria.acciones).isEmpty();
    }

    @Test
    void rechazadoConservaSuResultadoYRespondeSinEfecto() {
        sagas.saga = SagaProcesada.rechazada(SAGA, CAMPANIA, LABOR, "CAMPANIA_FINALIZADA", "Finalizada", AHORA);

        RespuestaSaga respuesta = anular();

        assertThat(respuesta.tipo()).isEqualTo(RespuestaSaga.ANULADO);
        assertThat(respuesta.datos()).containsEntry("sinEfecto", true);
        assertThat(sagas.saga.getResultado()).isEqualTo(ResultadoSagaProcesada.RECHAZADO);
    }

    @Test
    void yaAnuladoRepiteLaMismaRespuestaSinEfectosNuevos() {
        prepararRegistrada(EstadoCampania.EN_CURSO);
        RespuestaSaga primera = anular();

        RespuestaSaga segunda = anular();

        assertThat(segunda).isEqualTo(primera);
        assertThat(campanias.guardadas).isEqualTo(1);
        assertThat(auditoria.acciones).hasSize(1);
    }

    @Test
    void anuladoSinRegistroPreviaRepiteSinEfecto() {
        RespuestaSaga primera = anular();

        assertThat(anular()).isEqualTo(primera);
    }

    private static final class CampaniasEnMemoria implements RepositorioCampania {

        private Campania campania;
        private int guardadas;

        @Override
        public Campania guardar(Campania campania) {
            guardadas++;
            return campania;
        }

        @Override
        public Optional<Campania> buscarPorId(UUID id) {
            return Optional.ofNullable(campania);
        }

        @Override
        public Pagina<Campania> listar(FiltrosCampania filtros, int pagina, int tamanio) {
            throw new UnsupportedOperationException();
        }

        @Override
        public boolean existeEnCursoEnParcela(UUID idParcela) {
            throw new UnsupportedOperationException();
        }

        @Override
        public Pagina<CostoCampania> listarCostos(
                UUID idCampania, CategoriaCosto categoria, OrigenCosto origen, int pagina, int tamanio) {
            throw new UnsupportedOperationException();
        }
    }

    private static final class SagasEnMemoria implements RepositorioSagaProcesada {

        private SagaProcesada saga;

        @Override
        public void bloquear(UUID idSaga) {
        }

        @Override
        public Optional<SagaProcesada> buscar(UUID idSaga) {
            return Optional.ofNullable(saga);
        }

        @Override
        public void guardar(SagaProcesada saga) {
            this.saga = saga;
        }

        @Override
        public void registrarMensaje(UUID idMensaje, UUID idSaga, Instant ahora) {
        }
    }

    private static final class AuditoriaEnMemoria implements RegistroAuditoria {

        private final List<AccionAuditoria> acciones = new ArrayList<>();

        @Override
        public void registrar(AccionAuditoria accion, String entidad, UUID idEntidad) {
            acciones.add(accion);
        }

        @Override
        public void registrarServicio(String actor, AccionAuditoria accion, String entidad, UUID idEntidad) {
            acciones.add(accion);
        }
    }
}
