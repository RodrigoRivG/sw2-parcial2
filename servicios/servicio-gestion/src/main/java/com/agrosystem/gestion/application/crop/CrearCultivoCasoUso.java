package com.agrosystem.gestion.application.crop;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.crop.Cultivo;
import com.agrosystem.gestion.domain.crop.RepositorioCultivo;
import java.time.Clock;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CrearCultivoCasoUso {

    private final RepositorioCultivo repositorio;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public CrearCultivoCasoUso(RepositorioCultivo repositorio, RegistroAuditoria auditoria, Clock reloj) {
        this.repositorio = repositorio;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    @Transactional
    public Cultivo ejecutar(DatosCultivo datos) {
        Cultivo cultivo = Cultivo.crear(
                datos.nombre(), datos.variedad(), datos.unidadMedida(), datos.descripcion(), reloj.instant());
        Cultivo guardado = repositorio.guardar(cultivo);
        auditoria.registrar(AccionAuditoria.CREAR, "CULTIVO", guardado.getId());
        return guardado;
    }
}
