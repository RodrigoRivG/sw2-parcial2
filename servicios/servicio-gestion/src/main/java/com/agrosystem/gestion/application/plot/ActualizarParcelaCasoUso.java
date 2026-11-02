package com.agrosystem.gestion.application.plot;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.plot.Parcela;
import com.agrosystem.gestion.domain.plot.RepositorioParcela;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.time.Clock;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ActualizarParcelaCasoUso {

    private final RepositorioParcela repositorio;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public ActualizarParcelaCasoUso(RepositorioParcela repositorio, RegistroAuditoria auditoria, Clock reloj) {
        this.repositorio = repositorio;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    @Transactional
    public Parcela ejecutar(UUID id, DatosParcela datos, long version) {
        Parcela parcela = repositorio.buscarPorId(id).orElseThrow(ParcelaNoEncontrada::excepcion);
        if (parcela.getVersion() != version) {
            throw new ExcepcionDominio(
                    "CONFLICTO_CONCURRENCIA",
                    "La parcela cambió desde que se leyó. Vuelva a consultarla.",
                    ExcepcionDominio.Tipo.CONFLICTO);
        }
        parcela.actualizar(
                datos.nombre(),
                new Hectareas(datos.superficieHectareas()),
                datos.ubicacion(),
                datos.descripcion(),
                reloj.instant());
        Parcela guardada = repositorio.guardar(parcela);
        auditoria.registrar(AccionAuditoria.MODIFICAR, "PARCELA", guardada.getId());
        return guardada;
    }
}
