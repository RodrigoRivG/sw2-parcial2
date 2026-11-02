package com.agrosystem.gestion.application.crop;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.crop.Cultivo;
import com.agrosystem.gestion.domain.crop.RepositorioCultivo;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import java.time.Clock;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ActualizarCultivoCasoUso {

    private final RepositorioCultivo repositorio;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public ActualizarCultivoCasoUso(RepositorioCultivo repositorio, RegistroAuditoria auditoria, Clock reloj) {
        this.repositorio = repositorio;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    @Transactional
    public Cultivo ejecutar(UUID id, DatosCultivo datos, long version) {
        Cultivo cultivo = repositorio.buscarPorId(id).orElseThrow(CultivoNoEncontrado::excepcion);
        if (cultivo.getVersion() != version) {
            throw new ExcepcionDominio(
                    "CONFLICTO_CONCURRENCIA",
                    "El cultivo cambió desde que se leyó. Vuelva a consultarlo.",
                    ExcepcionDominio.Tipo.CONFLICTO);
        }
        cultivo.actualizar(datos.nombre(), datos.variedad(), datos.descripcion(), reloj.instant());
        Cultivo guardado = repositorio.guardar(cultivo);
        auditoria.registrar(AccionAuditoria.MODIFICAR, "CULTIVO", guardado.getId());
        return guardado;
    }
}
