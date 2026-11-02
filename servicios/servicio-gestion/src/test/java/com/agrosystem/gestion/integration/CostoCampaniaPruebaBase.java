package com.agrosystem.gestion.integration;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import java.sql.Date;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.ResultActions;

abstract class CostoCampaniaPruebaBase extends CampaniaPruebaBase {

    static final String HOY = LocalDate.now(ZoneOffset.UTC).toString();

    @Autowired
    protected JdbcTemplate jdbc;

    protected String rutaCostos(String idCampania) {
        return RUTA + "/" + idCampania + "/costos";
    }

    protected String cuerpoCosto(String categoria, String monto, String fecha, String descripcion) {
        return "{\"categoria\": \"" + categoria + "\", \"monto\": \"" + monto + "\", \"fecha\": \""
                + fecha + "\", \"descripcion\": \"" + descripcion + "\"}";
    }

    protected ResultActions registrar(String idCampania, String cuerpo, String rol) throws Exception {
        return mockMvc.perform(post(rutaCostos(idCampania)).with(conRol(rol))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpo));
    }

    protected String registrarCosto(String idCampania, String categoria, String monto) throws Exception {
        return crearEn(rutaCostos(idCampania), cuerpoCosto(categoria, monto, HOY, "Costo de prueba"));
    }

    /** La Saga todavía no existe: sus costos se insertan directamente en la base. */
    protected UUID insertarCostoSaga(String idCampania, String monto, boolean anulado) {
        UUID id = UUID.randomUUID();
        Timestamp ahora = Timestamp.from(Instant.now());
        jdbc.update("INSERT INTO costo_campania (id, id_campania, categoria, monto, fecha, descripcion, origen, "
                + "id_saga, id_labor, anulado, fecha_anulacion, fecha_registro) VALUES "
                + "(?, ?, 'INSUMO', CAST(? AS NUMERIC), ?, 'Insumos de la labor', 'SAGA', ?, ?, ?, ?, ?)",
                id,
                UUID.fromString(idCampania),
                monto,
                Date.valueOf(HOY),
                UUID.randomUUID(),
                UUID.randomUUID(),
                anulado,
                anulado ? ahora : null,
                ahora);
        return id;
    }
}
