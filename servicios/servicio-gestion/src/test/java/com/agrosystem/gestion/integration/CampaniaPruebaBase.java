package com.agrosystem.gestion.integration;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.shared.Hectareas;
import com.agrosystem.gestion.infrastructure.persistence.CampaniaSpringData;
import com.agrosystem.gestion.infrastructure.persistence.CultivoSpringData;
import com.agrosystem.gestion.infrastructure.persistence.ParcelaSpringData;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;

abstract class CampaniaPruebaBase extends PruebaIntegracionBase {

    static final String RUTA = "/api/gestion/v1/campanias";
    static final String INICIO = "2026-11-15";
    static final String FIN = "2027-03-30";

    @Autowired
    protected ObjectMapper mapeador;

    @Autowired
    protected CampaniaSpringData campanias;

    @Autowired
    protected RepositorioCampania repositorioCampania;

    @Autowired
    protected ParcelaSpringData parcelas;

    @Autowired
    protected CultivoSpringData cultivos;

    protected String idParcela;
    protected String idCultivo;

    /** Se limpia también al terminar: las claves foráneas impedirían vaciar parcelas en otros tests. */
    @BeforeEach
    void prepararDatos() throws Exception {
        vaciarDatos();
        idParcela = crearParcela("Lote Norte", "25.5");
        idCultivo = crearCultivo("Soya");
    }

    @AfterEach
    void vaciarDatos() {
        campanias.deleteAllInBatch();
        parcelas.deleteAllInBatch();
        cultivos.deleteAllInBatch();
    }

    protected String crearParcela(String nombre, String superficie) throws Exception {
        return crearEn("/api/gestion/v1/parcelas",
                "{\"nombre\": \"" + nombre + "\", \"superficieHectareas\": \"" + superficie + "\"}");
    }

    protected String crearCultivo(String nombre) throws Exception {
        return crearEn("/api/gestion/v1/cultivos",
                "{\"nombre\": \"" + nombre + "\", \"unidadMedida\": \"KILOGRAMO\"}");
    }

    protected String crearEn(String ruta, String cuerpo) throws Exception {
        return crearJson(ruta, cuerpo).get("id").asText();
    }

    protected JsonNode crearJson(String ruta, String cuerpo) throws Exception {
        String respuesta = mockMvc.perform(post(ruta).with(conRol("administrador"))
                        .contentType(MediaType.APPLICATION_JSON).content(cuerpo))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return mapeador.readTree(respuesta);
    }

    protected String cuerpo(String nombre, String parcela, String cultivo, String inicio, String fin) {
        return "{\"nombre\": \"" + nombre + "\", \"idParcela\": \"" + parcela + "\", \"idCultivo\": \""
                + cultivo + "\", \"fechaInicio\": \"" + inicio + "\", \"fechaFin\": \"" + fin + "\"}";
    }

    protected String cuerpoConVersion(
            String nombre, String parcela, String cultivo, String inicio, String fin, long version) {
        return "{\"nombre\": \"" + nombre + "\", \"idParcela\": \"" + parcela + "\", \"idCultivo\": \""
                + cultivo + "\", \"fechaInicio\": \"" + inicio + "\", \"fechaFin\": \"" + fin
                + "\", \"version\": " + version + "}";
    }

    protected String crearCampania(String nombre) throws Exception {
        return crearEn(RUTA, cuerpo(nombre, idParcela, idCultivo, INICIO, FIN));
    }

    protected String cuerpoEstado(String destino, long version) {
        return "{\"estadoDestino\": \"" + destino + "\", \"version\": " + version + "}";
    }

    protected void iniciar(String id) throws Exception {
        mockMvc.perform(put(RUTA + "/" + id + "/estado").with(conRol("administrador"))
                        .contentType(MediaType.APPLICATION_JSON).content(cuerpoEstado("EN_CURSO", 0)))
                .andExpect(status().isOk());
    }

    /** Todavía no hay API para finalizar sin producción: la campaña se guarda directamente. */
    protected String crearFinalizada(String nombre) {
        Instant ahora = Instant.now();
        Campania campania = Campania.reconstruir(
                UUID.randomUUID(),
                nombre,
                UUID.fromString(idParcela),
                UUID.fromString(idCultivo),
                LocalDate.parse(INICIO),
                LocalDate.parse(FIN),
                new Hectareas(new BigDecimal("25.5")),
                EstadoCampania.FINALIZADA,
                ahora,
                ahora,
                null,
                ahora,
                ahora);
        return repositorioCampania.guardar(campania).getId().toString();
    }
}
