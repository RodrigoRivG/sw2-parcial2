package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.application.campaign.ConsultaEstadoCampania;
import com.agrosystem.gestion.application.campaign.EstadoResumidoCampania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import java.time.LocalDate;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class ConsultaEstadoCampaniaJdbc implements ConsultaEstadoCampania {

    private static final String CONSULTA =
            "SELECT id, id_parcela, id_cultivo, estado, fecha_inicio, fecha_fin FROM campania WHERE id = ?";

    private final JdbcTemplate jdbc;

    public ConsultaEstadoCampaniaJdbc(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public Optional<EstadoResumidoCampania> buscar(UUID id) {
        return jdbc.query(CONSULTA, (fila, numero) -> new EstadoResumidoCampania(
                        fila.getObject("id", UUID.class),
                        fila.getObject("id_parcela", UUID.class),
                        fila.getObject("id_cultivo", UUID.class),
                        EstadoCampania.valueOf(fila.getString("estado")),
                        fila.getObject("fecha_inicio", LocalDate.class),
                        fila.getObject("fecha_fin", LocalDate.class)), id)
                .stream()
                .findFirst();
    }
}
