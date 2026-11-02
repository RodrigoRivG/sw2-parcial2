package com.agrosystem.gestion.application.plot;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.plot.Parcela;
import com.agrosystem.gestion.domain.plot.RepositorioParcela;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Hectareas;
import com.agrosystem.gestion.domain.shared.Pagina;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ActualizarParcelaCasoUsoTest {

    private static final Instant AHORA = Instant.parse("2026-11-02T14:00:00Z");
    private static final DatosParcela DATOS =
            new DatosParcela("Lote Sur", new BigDecimal("27"), "Km 20", null);

    private final RepositorioEnMemoria repositorio = new RepositorioEnMemoria();
    private final AuditoriaEnMemoria auditoria = new AuditoriaEnMemoria();
    private final ActualizarParcelaCasoUso casoUso =
            new ActualizarParcelaCasoUso(repositorio, auditoria, Clock.fixed(AHORA, ZoneOffset.UTC));

    private Parcela parcelaConVersion(long version) {
        Parcela parcela = Parcela.reconstruir(
                UUID.randomUUID(),
                "Lote Norte",
                new Hectareas(new BigDecimal("25.5")),
                null,
                null,
                version,
                AHORA.minusSeconds(60),
                AHORA.minusSeconds(60));
        repositorio.parcela = parcela;
        return parcela;
    }

    @Test
    void siNoExisteLanzaParcelaNoEncontrada() {
        assertThatThrownBy(() -> casoUso.ejecutar(UUID.randomUUID(), DATOS, 0))
                .isInstanceOfSatisfying(ExcepcionDominio.class, error ->
                        assertThat(error.getCodigo()).isEqualTo("PARCELA_NO_ENCONTRADA"));
        assertThat(auditoria.acciones).isEmpty();
    }

    @Test
    void siLaVersionDifiereLanzaConflictoYNoGuarda() {
        Parcela parcela = parcelaConVersion(3);

        assertThatThrownBy(() -> casoUso.ejecutar(parcela.getId(), DATOS, 2))
                .isInstanceOfSatisfying(ExcepcionDominio.class, error -> {
                    assertThat(error.getCodigo()).isEqualTo("CONFLICTO_CONCURRENCIA");
                    assertThat(error.getTipo()).isEqualTo(ExcepcionDominio.Tipo.CONFLICTO);
                });
        assertThat(repositorio.guardados).isZero();
        assertThat(auditoria.acciones).isEmpty();
    }

    @Test
    void actualizaGuardaYAudita() {
        Parcela parcela = parcelaConVersion(3);

        Parcela resultado = casoUso.ejecutar(parcela.getId(), DATOS, 3);

        assertThat(resultado.getNombre()).isEqualTo("Lote Sur");
        assertThat(resultado.getFechaActualizacion()).isEqualTo(AHORA);
        assertThat(repositorio.guardados).isEqualTo(1);
        assertThat(auditoria.acciones).containsExactly(AccionAuditoria.MODIFICAR);
    }

    private static final class RepositorioEnMemoria implements RepositorioParcela {

        private Parcela parcela;
        private int guardados;

        @Override
        public Parcela guardar(Parcela parcela) {
            guardados++;
            return parcela;
        }

        @Override
        public Optional<Parcela> buscarPorId(UUID id) {
            return Optional.ofNullable(parcela).filter(guardada -> guardada.getId().equals(id));
        }

        @Override
        public Pagina<Parcela> listar(String filtroNombre, int pagina, int tamanio) {
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
