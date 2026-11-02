package com.agrosystem.gestion.application.campaign;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.campaign.CostoCampania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.FiltrosCampania;
import com.agrosystem.gestion.domain.campaign.OrigenCosto;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
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

class CambiarEstadoCampaniaCasoUsoTest {

    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");

    private final RepositorioEnMemoria repositorio = new RepositorioEnMemoria();
    private final AuditoriaEnMemoria auditoria = new AuditoriaEnMemoria();
    private final CambiarEstadoCampaniaCasoUso casoUso =
            new CambiarEstadoCampaniaCasoUso(repositorio, auditoria, Clock.fixed(AHORA, ZoneOffset.UTC));

    private Campania campaniaEn(EstadoCampania estado) {
        Campania campania = Campania.reconstruir(
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
                3L,
                AHORA.minusSeconds(60),
                AHORA.minusSeconds(60),
                List.of());
        repositorio.campania = campania;
        return campania;
    }

    private void esperarCodigo(UUID id, EstadoCampania destino, long version, String codigo) {
        assertThatThrownBy(() -> casoUso.ejecutar(id, destino, version))
                .isInstanceOfSatisfying(ExcepcionDominio.class, error ->
                        assertThat(error.getCodigo()).isEqualTo(codigo));
        assertThat(repositorio.guardados).isZero();
        assertThat(auditoria.acciones).isEmpty();
    }

    @Test
    void siLaParcelaYaTieneOtraEnCursoSeRechaza() {
        Campania campania = campaniaEn(EstadoCampania.PLANIFICADA);
        repositorio.hayOtraEnCurso = true;

        esperarCodigo(campania.getId(), EstadoCampania.EN_CURSO, 3, "PARCELA_CON_CAMPANIA_EN_CURSO");
    }

    @Test
    void laMismaCampaniaEnCursoRecibeTransicionInvalidaNoConflictoDeParcela() {
        Campania campania = campaniaEn(EstadoCampania.EN_CURSO);
        repositorio.hayOtraEnCurso = true;

        esperarCodigo(campania.getId(), EstadoCampania.EN_CURSO, 3, "TRANSICION_ESTADO_INVALIDA");
    }

    @Test
    void siNoExisteOLaVersionDifiereSeRechaza() {
        Campania campania = campaniaEn(EstadoCampania.PLANIFICADA);

        esperarCodigo(UUID.randomUUID(), EstadoCampania.EN_CURSO, 3, "CAMPANIA_NO_ENCONTRADA");
        esperarCodigo(campania.getId(), EstadoCampania.EN_CURSO, 2, "CONFLICTO_CONCURRENCIA");
    }

    @Test
    void cambiaElEstadoGuardaYAudita() {
        Campania campania = campaniaEn(EstadoCampania.PLANIFICADA);

        Campania resultado = casoUso.ejecutar(campania.getId(), EstadoCampania.EN_CURSO, 3);

        assertThat(resultado.getEstado()).isEqualTo(EstadoCampania.EN_CURSO);
        assertThat(resultado.getFechaInicioEjecucion()).isEqualTo(AHORA);
        assertThat(repositorio.guardados).isEqualTo(1);
        assertThat(auditoria.acciones).containsExactly(AccionAuditoria.CAMBIAR_ESTADO);
    }

    private static final class RepositorioEnMemoria implements RepositorioCampania {

        private Campania campania;
        private boolean hayOtraEnCurso;
        private int guardados;

        @Override
        public Campania guardar(Campania campania) {
            guardados++;
            return campania;
        }

        @Override
        public Optional<Campania> buscarPorId(UUID id) {
            return Optional.ofNullable(campania).filter(guardada -> guardada.getId().equals(id));
        }

        @Override
        public Pagina<Campania> listar(FiltrosCampania filtros, int pagina, int tamanio) {
            throw new UnsupportedOperationException();
        }

        @Override
        public boolean existeEnCursoEnParcela(UUID idParcela) {
            return hayOtraEnCurso;
        }

        @Override
        public Pagina<CostoCampania> listarCostos(
                UUID idCampania, CategoriaCosto categoria, OrigenCosto origen, int pagina, int tamanio) {
            throw new UnsupportedOperationException();
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
