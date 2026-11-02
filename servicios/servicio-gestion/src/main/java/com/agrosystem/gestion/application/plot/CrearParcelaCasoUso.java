package com.agrosystem.gestion.application.plot;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.plot.Parcela;
import com.agrosystem.gestion.domain.plot.RepositorioParcela;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.time.Clock;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CrearParcelaCasoUso {

    private final RepositorioParcela repositorio;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public CrearParcelaCasoUso(RepositorioParcela repositorio, RegistroAuditoria auditoria, Clock reloj) {
        this.repositorio = repositorio;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    @Transactional
    public Parcela ejecutar(DatosParcela datos) {
        Parcela parcela = Parcela.crear(
                datos.nombre(),
                new Hectareas(datos.superficieHectareas()),
                datos.ubicacion(),
                datos.descripcion(),
                reloj.instant());
        Parcela guardada = repositorio.guardar(parcela);
        auditoria.registrar(AccionAuditoria.CREAR, "PARCELA", guardada.getId());
        return guardada;
    }
}
