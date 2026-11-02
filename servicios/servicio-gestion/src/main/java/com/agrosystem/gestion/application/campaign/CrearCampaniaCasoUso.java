package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.application.crop.CultivoNoEncontrado;
import com.agrosystem.gestion.application.plot.ParcelaNoEncontrada;
import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.crop.RepositorioCultivo;
import com.agrosystem.gestion.domain.plot.Parcela;
import com.agrosystem.gestion.domain.plot.RepositorioParcela;
import java.time.Clock;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CrearCampaniaCasoUso {

    private final RepositorioCampania campanias;
    private final RepositorioParcela parcelas;
    private final RepositorioCultivo cultivos;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public CrearCampaniaCasoUso(
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
    public Campania ejecutar(DatosCampania datos) {
        Parcela parcela = parcelas.buscarPorId(datos.idParcela()).orElseThrow(ParcelaNoEncontrada::excepcion);
        cultivos.buscarPorId(datos.idCultivo()).orElseThrow(CultivoNoEncontrado::excepcion);
        Campania campania = Campania.crear(
                datos.nombre(),
                datos.idParcela(),
                datos.idCultivo(),
                datos.fechaInicio(),
                datos.fechaFin(),
                parcela.getSuperficie(),
                reloj.instant());
        Campania guardada = campanias.guardar(campania);
        auditoria.registrar(AccionAuditoria.CREAR, "CAMPANIA", guardada.getId());
        return guardada;
    }
}
