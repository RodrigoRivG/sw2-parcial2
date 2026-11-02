package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.agrosystem.gestion.infrastructure.persistence.RegistroAuditoriaSpringData;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.ResultActions;

class CultivoControladorIT extends CultivoPruebaBase {

    @Autowired
    private ObjectMapper mapeador;

    @Autowired
    private RegistroAuditoriaSpringData auditoria;

    private ResultActions crear(String cuerpo, String rol) throws Exception {
        return mockMvc.perform(post(RUTA).with(conRol(rol))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpo));
    }

    private JsonNode crearValido(String nombre, String variedad) throws Exception {
        String respuesta = crear(cuerpo(nombre, variedad), "administrador")
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return mapeador.readTree(respuesta);
    }

    private ResultActions modificar(String id, String cuerpo, String rol) throws Exception {
        return mockMvc.perform(put(RUTA + "/" + id).with(conRol(rol))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpo));
    }

    private void verificarAuditoria(String id, String accion) {
        assertThat(auditoria.findAll())
                .filteredOn(registro -> registro.getIdEntidad().equals(UUID.fromString(id)))
                .filteredOn(registro -> registro.getAccion().equals(accion))
                .hasSize(1)
                .first()
                .satisfies(registro -> {
                    assertThat(registro.getActor()).isEqualTo("usuario-administrador");
                    assertThat(registro.getEntidad()).isEqualTo("CULTIVO");
                });
    }

    // Historia 1

    @Test
    void administradorRegistraUnCultivo() throws Exception {
        String respuesta = crear("{\"nombre\": \"Soya\", \"variedad\": \"Munasqa\", "
                + "\"unidadMedida\": \"KILOGRAMO\", \"descripcion\": \"Ciclo de verano\"}", "administrador")
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", containsString("/api/gestion/v1/cultivos/")))
                .andExpect(jsonPath("$.id").isNotEmpty())
                .andExpect(jsonPath("$.nombre").value("Soya"))
                .andExpect(jsonPath("$.variedad").value("Munasqa"))
                .andExpect(jsonPath("$.unidadMedida").value("KILOGRAMO"))
                .andExpect(jsonPath("$.descripcion").value("Ciclo de verano"))
                .andExpect(jsonPath("$.version").value(0))
                .andExpect(jsonPath("$.fechaCreacion").isNotEmpty())
                .andReturn().getResponse().getContentAsString();

        verificarAuditoria(mapeador.readTree(respuesta).get("id").asText(), "CREAR");
    }

    @Test
    void mismoNombreYVariedadSinDistinguirMayusculasSeRechaza() throws Exception {
        crearValido("Soya", "Munasqa");

        crear(cuerpo("soya", "munasqa"), "administrador")
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.codigo").value("CULTIVO_DUPLICADO"));
    }

    @Test
    void mismoNombreConOtraVariedadOSinVariedadSeAcepta() throws Exception {
        crearValido("Soya", "Munasqa");
        crearValido("Soya", "Otra");
        crearValido("Soya", null);

        assertThat(cultivos.count()).isEqualTo(3);
    }

    @Test
    void variedadEnBlancoCuentaComoSinVariedad() throws Exception {
        crear(cuerpo("Soya", "   "), "administrador")
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.variedad").value(nullValue()));

        crear(cuerpo("SOYA", null), "administrador")
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.codigo").value("CULTIVO_DUPLICADO"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"gerencia", "tecnico_campo", "lectura_gestion"})
    void soloElAdministradorPuedeRegistrar(String rol) throws Exception {
        crear(cuerpo("Soya", null), rol)
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.codigo").value("SIN_PERMISO"));
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "{\"nombre\": \"Soya\", \"unidadMedida\": \"QUINTAL\"}",
            "{\"nombre\": \"Soya\", \"unidadMedida\": 0}",
            "{\"nombre\": \"Soya\"}",
            "{\"unidadMedida\": \"KILOGRAMO\"}",
            "{\"nombre\": \"   \", \"unidadMedida\": \"KILOGRAMO\"}"
    })
    void formatoInvalidoResponde400(String cuerpo) throws Exception {
        crear(cuerpo, "administrador")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"))
                .andExpect(jsonPath("$.detalles[0].campo").isNotEmpty());
        assertThat(cultivos.count()).isZero();
    }

    @Test
    void recortaElNombreAntesDeValidarSuLongitud() throws Exception {
        String cienCaracteres = "a".repeat(100);

        crear(cuerpo("  " + cienCaracteres + "  ", null), "administrador")
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.nombre").value(cienCaracteres));
        crear(cuerpo("b".repeat(101), null), "administrador")
                .andExpect(status().isBadRequest());
    }

    // Historia 2

    @Test
    void listaPaginadoYOrdenadoPorNombreYVariedad() throws Exception {
        crearValido("Trigo", "B");
        crearValido("Soya", "Z");
        crearValido("Soya", "A");

        mockMvc.perform(get(RUTA).with(conRol("gerencia")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(3)))
                .andExpect(jsonPath("$.items[0].variedad").value("A"))
                .andExpect(jsonPath("$.items[1].variedad").value("Z"))
                .andExpect(jsonPath("$.items[2].nombre").value("Trigo"))
                .andExpect(jsonPath("$.total").value(3));

        mockMvc.perform(get(RUTA + "?tamanio=1&pagina=1").with(conRol("gerencia")))
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].variedad").value("Z"))
                .andExpect(jsonPath("$.total").value(3));
    }

    @Test
    void filtraPorTextoEnElNombre() throws Exception {
        crearValido("Soya", null);
        crearValido("Trigo", null);

        mockMvc.perform(get(RUTA + "?nombre=SOY").with(conRol("administrador")))
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].nombre").value("Soya"));
    }

    @Test
    void idInexistenteResponde404() throws Exception {
        mockMvc.perform(get(RUTA + "/" + UUID.randomUUID()).with(conRol("administrador")))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.codigo").value("CULTIVO_NO_ENCONTRADO"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"administrador", "gerencia", "lectura_gestion"})
    void losRolesDeLecturaVenListadoYDetalle(String rol) throws Exception {
        String id = crearValido("Soya", "Munasqa").get("id").asText();

        mockMvc.perform(get(RUTA).with(conRol(rol))).andExpect(status().isOk());
        mockMvc.perform(get(RUTA + "/" + id).with(conRol(rol)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.unidadMedida").value("KILOGRAMO"));
    }

    @Test
    void tecnicoDeCampoNoConsultaElCatalogo() throws Exception {
        mockMvc.perform(get(RUTA).with(conRol("tecnico_campo")))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.codigo").value("SIN_PERMISO"));
    }

    // Historia 3

    @Test
    void administradorRenombraUnCultivoYQuedaAuditado() throws Exception {
        String id = crearValido("Soja", "A").get("id").asText();

        modificar(id, cuerpoConVersion("Soya", "A", 0), "administrador")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nombre").value("Soya"))
                .andExpect(jsonPath("$.version").value(1));

        mockMvc.perform(get(RUTA + "/" + id).with(conRol("gerencia")))
                .andExpect(jsonPath("$.nombre").value("Soya"));
        verificarAuditoria(id, "MODIFICAR");
    }

    @Test
    void combinacionExistenteSeRechazaAlModificar() throws Exception {
        crearValido("Soya", "A");
        String id = crearValido("Soya", "B").get("id").asText();

        modificar(id, cuerpoConVersion("SOYA", "a", 0), "administrador")
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.codigo").value("CULTIVO_DUPLICADO"));
    }

    @Test
    void versionDesactualizadaResponde409() throws Exception {
        String id = crearValido("Soya", null).get("id").asText();
        modificar(id, cuerpoConVersion("Soya", "A", 0), "administrador").andExpect(status().isOk());

        modificar(id, cuerpoConVersion("Soya", "B", 0), "administrador")
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.codigo").value("CONFLICTO_CONCURRENCIA"));
    }

    @Test
    void modificarConDatosInvalidosInexistenteOSinPermiso() throws Exception {
        String id = crearValido("Soya", null).get("id").asText();

        modificar(id, cuerpo("Soya", null), "administrador")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.detalles[0].campo").value("version"));
        modificar(UUID.randomUUID().toString(), cuerpoConVersion("Otro", null, 0), "administrador")
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.codigo").value("CULTIVO_NO_ENCONTRADO"));
        modificar(id, cuerpoConVersion("Soya", "A", 0), "gerencia")
                .andExpect(status().isForbidden());
    }

    // OpenAPI

    @Test
    void openApiListaLosEndpointsConSusErrores() throws Exception {
        String documento = mockMvc.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        JsonNode rutas = mapeador.readTree(documento).get("paths");

        assertThat(rutas.get(RUTA).get("post").get("responses").get("409").get("description").asText())
                .isEqualTo("CULTIVO_DUPLICADO");
        assertThat(rutas.get(RUTA).get("get").get("responses").has("400")).isTrue();
        assertThat(rutas.get(RUTA + "/{id}").get("get").get("responses").get("404").get("description").asText())
                .isEqualTo("CULTIVO_NO_ENCONTRADO");
        assertThat(rutas.get(RUTA + "/{id}").get("put").get("responses").get("409").get("description").asText())
                .contains("CONFLICTO_CONCURRENCIA");
    }
}
