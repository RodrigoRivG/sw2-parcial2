package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.agrosystem.gestion.infrastructure.persistence.RegistroAuditoriaSpringData;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.ResultActions;

class CostoCampaniaControladorIT extends CostoCampaniaPruebaBase {

    @Autowired
    private RegistroAuditoriaSpringData auditoria;

    private ResultActions modificar(String campania, Object costo, String cuerpo, String rol) throws Exception {
        return mockMvc.perform(put(rutaCostos(campania) + "/" + costo).with(conRol(rol))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpo));
    }

    private ResultActions eliminar(String campania, Object costo, String rol) throws Exception {
        return mockMvc.perform(delete(rutaCostos(campania) + "/" + costo).with(conRol(rol)));
    }

    private void esperarError(ResultActions resultado, int estado, String codigo) throws Exception {
        resultado.andExpect(status().is(estado)).andExpect(jsonPath("$.codigo").value(codigo));
    }

    private void verificarAuditoria(String id, String accion) {
        assertThat(auditoria.findAll())
                .filteredOn(registro -> registro.getIdEntidad().equals(UUID.fromString(id)))
                .filteredOn(registro -> registro.getAccion().equals(accion))
                .hasSize(1)
                .first()
                .satisfies(registro -> {
                    assertThat(registro.getActor()).isEqualTo("usuario-administrador");
                    assertThat(registro.getEntidad()).isEqualTo("COSTO_CAMPANIA");
                });
    }

    // Historia 1

    @Test
    void administradorRegistraUnCostoYAumentaElTotal() throws Exception {
        String campania = crearCampania("Soya");
        iniciar(campania);

        String respuesta = registrar(campania, cuerpoCosto("MANO_DE_OBRA", "1500.00", "2026-10-10", "Cosecha manual"), "administrador")
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", containsString("/costos/")))
                .andExpect(jsonPath("$.id").isNotEmpty())
                .andExpect(jsonPath("$.categoria").value("MANO_DE_OBRA"))
                .andExpect(jsonPath("$.monto").value("1500.00"))
                .andExpect(jsonPath("$.fecha").value("2026-10-10"))
                .andExpect(jsonPath("$.descripcion").value("Cosecha manual"))
                .andExpect(jsonPath("$.origen").value("MANUAL"))
                .andExpect(jsonPath("$.idLabor").value(nullValue()))
                .andExpect(jsonPath("$.fechaRegistro").isNotEmpty())
                .andReturn().getResponse().getContentAsString();

        verificarAuditoria(mapeador.readTree(respuesta).get("id").asText(), "CREAR");
        mockMvc.perform(get(RUTA + "/" + campania).with(conRol("gerencia")))
                .andExpect(jsonPath("$.resumen.costoTotal").value("1500.00"))
                .andExpect(jsonPath("$.resumen.cantidadCostos").value(1));
    }

    @Test
    void enPlanificadaSeAcepta() throws Exception {
        registrar(crearCampania("Soya"), cuerpoCosto("MAQUINARIA", "10", HOY, "Arado"), "administrador")
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.monto").value("10.00"));
    }

    @Test
    void enFinalizadaSeRechaza() throws Exception {
        esperarError(registrar(crearFinalizada("Cerrada"), cuerpoCosto("OTRO", "10", HOY, "x"), "administrador"),
                422, "CAMPANIA_FINALIZADA");
    }

    @ParameterizedTest
    @ValueSource(strings = {"0", "-5.00"})
    void montoCeroONegativoSeRechaza(String monto) throws Exception {
        esperarError(registrar(crearCampania("Soya"), cuerpoCosto("OTRO", monto, HOY, "x"), "administrador"),
                422, "MONTO_INVALIDO");
    }

    @ParameterizedTest
    @ValueSource(strings = {"gerencia", "tecnico_campo", "lectura_gestion"})
    void soloElAdministradorRegistra(String rol) throws Exception {
        esperarError(registrar(crearCampania("Soya"), cuerpoCosto("OTRO", "1", HOY, "x"), rol), 403, "SIN_PERMISO");
    }

    @Test
    void casosBordeDeFormatoYFecha() throws Exception {
        String campania = crearCampania("Soya");
        String manana = LocalDate.now(ZoneOffset.UTC).plusDays(2).toString();

        esperarError(registrar(campania, cuerpoCosto("OTRO", "1.234", HOY, "x"), "administrador"), 400, "DATOS_INVALIDOS");
        esperarError(registrar(campania, cuerpoCosto("NO_EXISTE", "1", HOY, "x"), "administrador"), 400, "DATOS_INVALIDOS");
        esperarError(registrar(campania, cuerpoCosto("OTRO", "1", HOY, "  "), "administrador"), 400, "DATOS_INVALIDOS");
        esperarError(registrar(campania, "{\"categoria\": \"OTRO\", \"monto\": 10, \"fecha\": \"" + HOY
                + "\", \"descripcion\": \"x\"}", "administrador"), 400, "DATOS_INVALIDOS");
        esperarError(registrar(campania, cuerpoCosto("OTRO", "1", manana, "x"), "administrador"),
                422, "FECHA_COSTO_INVALIDA");
        esperarError(registrar(UUID.randomUUID().toString(), cuerpoCosto("OTRO", "1", HOY, "x"), "administrador"),
                404, "CAMPANIA_NO_ENCONTRADA");
    }

    @Test
    void costoPuedeTenerFechaAnteriorAlInicioDeLaCampania() throws Exception {
        registrar(crearCampania("Soya"), cuerpoCosto("OTRO", "1", "2020-01-01", "Preparacion"), "administrador")
                .andExpect(status().isCreated());
    }

    // Historia 2

    @Test
    void listaManualesYSagaConTotalesQueIgnoranLosFiltros() throws Exception {
        String campania = crearCampania("Soya");
        crearEn(rutaCostos(campania), cuerpoCosto("MANO_DE_OBRA", "1500.00", "2026-01-02", "Antiguo"));
        crearEn(rutaCostos(campania), cuerpoCosto("MANO_DE_OBRA", "0.10", "2026-01-03", "Reciente"));
        insertarCostoSaga(campania, "820.50", false);
        insertarCostoSaga(campania, "999.00", true);

        mockMvc.perform(get(rutaCostos(campania)).with(conRol("gerencia")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(3)))
                .andExpect(jsonPath("$.total").value(3))
                .andExpect(jsonPath("$.items[0].origen").value("SAGA"))
                .andExpect(jsonPath("$.items[0].idLabor").isNotEmpty())
                .andExpect(jsonPath("$.items[1].descripcion").value("Reciente"))
                .andExpect(jsonPath("$.items[2].descripcion").value("Antiguo"))
                .andExpect(jsonPath("$.costoTotal").value("2320.60"))
                .andExpect(jsonPath("$.subtotalesPorCategoria.MANO_DE_OBRA").value("1500.10"))
                .andExpect(jsonPath("$.subtotalesPorCategoria.INSUMO").value("820.50"))
                .andExpect(jsonPath("$.subtotalesPorCategoria.MAQUINARIA").value("0.00"))
                .andExpect(jsonPath("$.subtotalesPorCategoria.OTRO").value("0.00"));

        mockMvc.perform(get(rutaCostos(campania) + "?categoria=INSUMO").with(conRol("lectura_gestion")))
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].monto").value("820.50"))
                .andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.costoTotal").value("2320.60"));

        mockMvc.perform(get(rutaCostos(campania) + "?origen=MANUAL&tamanio=1&pagina=1").with(conRol("administrador")))
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].descripcion").value("Antiguo"))
                .andExpect(jsonPath("$.total").value(2));
    }

    @Test
    void lecturaConErroresYPermisos() throws Exception {
        String campania = crearCampania("Soya");

        esperarError(mockMvc.perform(get(rutaCostos(UUID.randomUUID().toString())).with(conRol("gerencia"))),
                404, "CAMPANIA_NO_ENCONTRADA");
        esperarError(mockMvc.perform(get(rutaCostos(campania) + "?categoria=OTRA").with(conRol("gerencia"))),
                400, "DATOS_INVALIDOS");
        esperarError(mockMvc.perform(get(rutaCostos(campania)).with(conRol("tecnico_campo"))), 403, "SIN_PERMISO");
    }

    // Historia 3

    @Test
    void corrigeUnCostoManualYQuedaAuditado() throws Exception {
        String campania = crearCampania("Soya");
        iniciar(campania);
        String costo = registrarCosto(campania, "OTRO", "100.00");

        modificar(campania, costo, cuerpoCosto("MAQUINARIA", "250.50", HOY, "  Corregido  "), "administrador")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.monto").value("250.50"))
                .andExpect(jsonPath("$.categoria").value("MAQUINARIA"))
                .andExpect(jsonPath("$.descripcion").value("Corregido"));

        verificarAuditoria(costo, "MODIFICAR");
        mockMvc.perform(get(rutaCostos(campania)).with(conRol("gerencia")))
                .andExpect(jsonPath("$.costoTotal").value("250.50"))
                .andExpect(jsonPath("$.subtotalesPorCategoria.OTRO").value("0.00"));
    }

    @Test
    void eliminaUnCostoManualYQuedaAuditado() throws Exception {
        String campania = crearCampania("Soya");
        iniciar(campania);
        String costo = registrarCosto(campania, "OTRO", "100.00");
        registrarCosto(campania, "OTRO", "5.00");

        eliminar(campania, costo, "administrador").andExpect(status().isNoContent());

        verificarAuditoria(costo, "ELIMINAR");
        mockMvc.perform(get(rutaCostos(campania)).with(conRol("gerencia")))
                .andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.costoTotal").value("5.00"));
        assertThat(jdbc.queryForObject("SELECT count(*) FROM costo_campania WHERE id = ?", Long.class, UUID.fromString(costo)))
                .isZero();
    }

    @Test
    void costosDeLaSagaNoSePuedenAlterarPorLaApi() throws Exception {
        String campania = crearCampania("Soya");
        UUID costo = insertarCostoSaga(campania, "820.50", false);

        esperarError(modificar(campania, costo, cuerpoCosto("OTRO", "1", HOY, "x"), "administrador"),
                422, "COSTO_NO_EDITABLE");
        esperarError(eliminar(campania, costo, "administrador"), 422, "COSTO_NO_EDITABLE");

        mockMvc.perform(get(rutaCostos(campania)).with(conRol("gerencia")))
                .andExpect(jsonPath("$.costoTotal").value("820.50"));
    }

    @Test
    void finalizadaNoAdmiteCambiosEnSusCostos() throws Exception {
        String campania = crearFinalizada("Cerrada");
        UUID costo = insertarCostoSaga(campania, "10.00", false);

        esperarError(modificar(campania, costo, cuerpoCosto("OTRO", "1", HOY, "x"), "administrador"),
                422, "CAMPANIA_FINALIZADA");
        esperarError(eliminar(campania, costo, "administrador"), 422, "CAMPANIA_FINALIZADA");
    }

    @Test
    void costoDeOtraCampaniaResponde404() throws Exception {
        String campania = crearCampania("Una");
        String otraCampania = crearCampania("Otra");
        String costo = registrarCosto(campania, "OTRO", "1.00");

        esperarError(modificar(otraCampania, costo, cuerpoCosto("OTRO", "2", HOY, "x"), "administrador"),
                404, "COSTO_NO_ENCONTRADO");
        esperarError(eliminar(otraCampania, costo, "administrador"), 404, "COSTO_NO_ENCONTRADO");
        esperarError(eliminar(campania, UUID.randomUUID(), "administrador"), 404, "COSTO_NO_ENCONTRADO");
    }

    @Test
    void modificarYEliminarExigenSerAdministrador() throws Exception {
        String campania = crearCampania("Soya");
        String costo = registrarCosto(campania, "OTRO", "1.00");

        esperarError(modificar(campania, costo, cuerpoCosto("OTRO", "2", HOY, "x"), "gerencia"), 403, "SIN_PERMISO");
        esperarError(eliminar(campania, costo, "gerencia"), 403, "SIN_PERMISO");
    }

    @Test
    void modificarValidaElMontoYLaFecha() throws Exception {
        String campania = crearCampania("Soya");
        String costo = registrarCosto(campania, "OTRO", "1.00");

        esperarError(modificar(campania, costo, cuerpoCosto("OTRO", "0", HOY, "x"), "administrador"),
                422, "MONTO_INVALIDO");
    }

    // Resumen de la campaña

    @Test
    void elDetalleDeLaCampaniaExcluyeLosCostosAnulados() throws Exception {
        String campania = crearCampania("Soya");
        registrarCosto(campania, "OTRO", "10.00");
        insertarCostoSaga(campania, "20.00", false);
        insertarCostoSaga(campania, "500.00", true);

        mockMvc.perform(get(RUTA + "/" + campania).with(conRol("gerencia")))
                .andExpect(jsonPath("$.resumen.costoTotal").value("30.00"))
                .andExpect(jsonPath("$.resumen.cantidadCostos").value(2));
    }

    @Test
    void cambiarDatosYEstadoConservaLosCostos() throws Exception {
        String campania = crearCampania("Soya");
        registrarCosto(campania, "OTRO", "10.00");
        JsonNode actual = mapeador.readTree(mockMvc.perform(get(RUTA + "/" + campania).with(conRol("gerencia")))
                .andReturn().getResponse().getContentAsString());

        mockMvc.perform(put(RUTA + "/" + campania + "/estado").with(conRol("administrador"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(cuerpoEstado("EN_CURSO", actual.get("version").asLong())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.resumen.costoTotal").value("10.00"));
    }

    // OpenAPI

    @Test
    void openApiListaLosEndpointsConSusErrores() throws Exception {
        String documento = mockMvc.perform(get("/v3/api-docs"))
                .andReturn().getResponse().getContentAsString();
        JsonNode rutas = mapeador.readTree(documento).get("paths");
        String coleccion = RUTA + "/{idCampania}/costos";

        assertThat(rutas.get(coleccion).get("post").get("responses").get("422").get("description").asText())
                .contains("MONTO_INVALIDO", "FECHA_COSTO_INVALIDA", "CAMPANIA_FINALIZADA");
        assertThat(rutas.get(coleccion).get("get").get("responses").get("404").get("description").asText())
                .isEqualTo("CAMPANIA_NO_ENCONTRADA");
        assertThat(rutas.get(coleccion + "/{idCosto}").get("put").get("responses").get("422").get("description").asText())
                .contains("COSTO_NO_EDITABLE");
        assertThat(rutas.get(coleccion + "/{idCosto}").get("delete").get("responses").has("204")).isTrue();
    }
}
