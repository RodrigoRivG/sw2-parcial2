package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.application.crop.CultivoNoEncontrado;
import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.ProduccionCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.crop.Cultivo;
import com.agrosystem.gestion.domain.crop.RepositorioCultivo;
import java.time.Clock;
import java.time.LocalDate;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RegistrarProduccionCasoUso {

    private final RepositorioCampania campanias;
    private final RepositorioCultivo cultivos;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public RegistrarProduccionCasoUso(
            RepositorioCampania campanias, RepositorioCultivo cultivos, RegistroAuditoria auditoria, Clock reloj) {
        this.campanias = campanias;
        this.cultivos = cultivos;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    /** Registrar de nuevo reemplaza la producción anterior (RQ-PRO-02). */
    @Transactional
    public ProduccionCampania ejecutar(UUID idCampania, DatosProduccion datos, String usuario) {
        Campania campania = campanias.buscarPorId(idCampania).orElseThrow(ErroresCampania::noEncontrada);
        Cultivo cultivo = cultivos.buscarPorId(campania.getIdCultivo()).orElseThrow(CultivoNoEncontrado::excepcion);
        boolean esCorreccion = campania.tieneProduccion();
        ProduccionCampania produccion = campania.registrarProduccion(
                datos.cantidad(),
                cultivo.getUnidadMedida(),
                datos.fechaCosecha(),
                datos.observaciones(),
                LocalDate.now(reloj),
                usuario,
                reloj.instant());
        campanias.guardar(campania);
        auditoria.registrar(
                esCorreccion ? AccionAuditoria.MODIFICAR : AccionAuditoria.CREAR, "PRODUCCION_CAMPANIA", idCampania);
        return produccion;
    }
}
