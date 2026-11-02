package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.application.crop.CultivoNoEncontrado;
import com.agrosystem.gestion.application.plot.ParcelaNoEncontrada;
import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.crop.RepositorioCultivo;
import com.agrosystem.gestion.domain.plot.RepositorioParcela;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.time.Clock;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ActualizarCampaniaCasoUso {

    private final RepositorioCampania campanias;
    private final RepositorioParcela parcelas;
    private final RepositorioCultivo cultivos;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public ActualizarCampaniaCasoUso(
            RepositorioCampania campanias,
            RepositorioParcela parcelas,
            RepositorioCultivo cultivos,
            RegistroAuditoria auditoria,
            Clock reloj) {
        this.campanias = campanias;
        this.parcelas = parcelas;
        this.cultivos = cultivos;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    @Transactional
    public Campania ejecutar(UUID id, DatosCampania datos, long version) {
        Campania campania = campanias.buscarPorId(id).orElseThrow(ErroresCampania::noEncontrada);
        if (campania.getVersion() != version) {
            throw ErroresCampania.conflictoVersion();
        }
        campania.actualizarDatos(
                datos.nombre(),
                datos.idParcela(),
                datos.idCultivo(),
                datos.fechaInicio(),
                datos.fechaFin(),
                superficieVigente(campania, datos),
                reloj.instant());
        Campania guardada = campanias.guardar(campania);
        auditoria.registrar(AccionAuditoria.MODIFICAR, "CAMPANIA", guardada.getId());
        return guardada;
    }

    /** Parcela y cultivo solo pueden cambiar en PLANIFICADA; en otro estado los rechaza el agregado. */
    private Hectareas superficieVigente(Campania campania, DatosCampania datos) {
        if (campania.getEstado() != EstadoCampania.PLANIFICADA) {
            return campania.getSuperficie();
        }
        if (!datos.idCultivo().equals(campania.getIdCultivo())) {
            cultivos.buscarPorId(datos.idCultivo()).orElseThrow(CultivoNoEncontrado::excepcion);
        }
        if (datos.idParcela().equals(campania.getIdParcela())) {
            return campania.getSuperficie();
        }
        return parcelas.buscarPorId(datos.idParcela())
                .orElseThrow(ParcelaNoEncontrada::excepcion)
                .getSuperficie();
    }
}
