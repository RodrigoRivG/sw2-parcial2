package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.application.campaign.ConsultaHistoricos;
import com.agrosystem.gestion.application.campaign.FilaHistorico;
import com.agrosystem.gestion.application.campaign.FiltrosHistoricos;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.Hectareas;
import com.agrosystem.gestion.domain.shared.Pagina;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

/** Una sola consulta por página: primero elige la página y luego suma en SQL solo los costos de esas campañas. */
@Repository
public class ConsultaHistoricosJdbc implements ConsultaHistoricos {

    private static final String COLUMNAS = """
            SELECT c.id, c.id_parcela, pa.nombre AS nombre_parcela, c.superficie_hectareas,
                   c.id_cultivo, cu.nombre AS nombre_cultivo, cu.variedad,
                   c.fecha_inicio, c.fecha_fin, c.fecha_inicio_ejecucion, c.fecha_finalizacion,
                   pr.cantidad AS produccion, pr.fecha_cosecha,
                   co.costo_total, co.costo_insumo, co.costo_mano_de_obra, co.costo_maquinaria, co.costo_otro
            FROM (SELECT * FROM campania c
            """;

    private static final String UNIONES = """
             ORDER BY c.fecha_finalizacion DESC, c.id
             LIMIT :limite OFFSET :desplazamiento) c
            JOIN parcela pa ON pa.id = c.id_parcela
            JOIN cultivo cu ON cu.id = c.id_cultivo
            LEFT JOIN produccion_campania pr ON pr.id_campania = c.id
            LEFT JOIN LATERAL (
                SELECT coalesce(sum(monto), 0) AS costo_total,
                       coalesce(sum(monto) FILTER (WHERE categoria = 'INSUMO'), 0) AS costo_insumo,
                       coalesce(sum(monto) FILTER (WHERE categoria = 'MANO_DE_OBRA'), 0) AS costo_mano_de_obra,
                       coalesce(sum(monto) FILTER (WHERE categoria = 'MAQUINARIA'), 0) AS costo_maquinaria,
                       coalesce(sum(monto) FILTER (WHERE categoria = 'OTRO'), 0) AS costo_otro
                FROM costo_campania
                WHERE id_campania = c.id AND NOT anulado
            ) co ON TRUE
            ORDER BY c.fecha_finalizacion DESC, c.id
            """;

    private final NamedParameterJdbcTemplate jdbc;

    public ConsultaHistoricosJdbc(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public Pagina<FilaHistorico> listar(FiltrosHistoricos filtros, int pagina, int tamanio) {
        MapSqlParameterSource parametros = new MapSqlParameterSource();
        String condiciones = condiciones(filtros, parametros);
        Long total = jdbc.queryForObject("SELECT count(*) FROM campania c" + condiciones, parametros, Long.class);
        parametros.addValue("limite", tamanio);
        parametros.addValue("desplazamiento", (long) pagina * tamanio);
        List<FilaHistorico> filas =
                jdbc.query(COLUMNAS + condiciones + UNIONES, parametros, (fila, numero) -> aFila(fila));
        return new Pagina<>(filas, total == null ? 0 : total);
    }

    /** Solo agrega las condiciones presentes; el rango cubre días completos en UTC. */
    private String condiciones(FiltrosHistoricos filtros, MapSqlParameterSource parametros) {
        List<String> lista = new ArrayList<>();
        lista.add("c.estado = 'FINALIZADA'");
        if (filtros.idCultivo() != null) {
            lista.add("c.id_cultivo = :idCultivo");
            parametros.addValue("idCultivo", filtros.idCultivo());
        }
        if (filtros.idParcela() != null) {
            lista.add("c.id_parcela = :idParcela");
            parametros.addValue("idParcela", filtros.idParcela());
        }
        if (filtros.fechaFinalizacionDesde() != null) {
            lista.add("c.fecha_finalizacion >= :desde");
            parametros.addValue("desde", inicioDelDia(filtros.fechaFinalizacionDesde()));
        }
        if (filtros.fechaFinalizacionHasta() != null) {
            lista.add("c.fecha_finalizacion < :hasta");
            parametros.addValue("hasta", inicioDelDia(filtros.fechaFinalizacionHasta().plusDays(1)));
        }
        return " WHERE " + String.join(" AND ", lista);
    }

    private OffsetDateTime inicioDelDia(LocalDate fecha) {
        return fecha.atStartOfDay().atOffset(ZoneOffset.UTC);
    }

    private FilaHistorico aFila(ResultSet fila) throws SQLException {
        Map<CategoriaCosto, Dinero> costos = new EnumMap<>(CategoriaCosto.class);
        costos.put(CategoriaCosto.INSUMO, dinero(fila, "costo_insumo"));
        costos.put(CategoriaCosto.MANO_DE_OBRA, dinero(fila, "costo_mano_de_obra"));
        costos.put(CategoriaCosto.MAQUINARIA, dinero(fila, "costo_maquinaria"));
        costos.put(CategoriaCosto.OTRO, dinero(fila, "costo_otro"));
        return new FilaHistorico(
                fila.getObject("id", UUID.class),
                fila.getObject("id_parcela", UUID.class),
                fila.getString("nombre_parcela"),
                new Hectareas(fila.getBigDecimal("superficie_hectareas")),
                fila.getObject("id_cultivo", UUID.class),
                fila.getString("nombre_cultivo"),
                fila.getString("variedad"),
                fila.getObject("fecha_inicio", LocalDate.class),
                fila.getObject("fecha_fin", LocalDate.class),
                instante(fila, "fecha_inicio_ejecucion"),
                instante(fila, "fecha_finalizacion"),
                fila.getBigDecimal("produccion"),
                fila.getObject("fecha_cosecha", LocalDate.class),
                dinero(fila, "costo_total"),
                costos);
    }

    private Dinero dinero(ResultSet fila, String columna) throws SQLException {
        return new Dinero(fila.getBigDecimal(columna));
    }

    private Instant instante(ResultSet fila, String columna) throws SQLException {
        OffsetDateTime valor = fila.getObject(columna, OffsetDateTime.class);
        return valor == null ? null : valor.toInstant();
    }
}
