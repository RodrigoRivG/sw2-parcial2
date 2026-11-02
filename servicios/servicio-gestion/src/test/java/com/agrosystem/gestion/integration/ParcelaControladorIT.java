package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.agrosystem.gestion.infrastructure.persistence.RegistroAuditoriaSpringData;
import com.agrosystem.gestion.infrastructure.persistence.entity.RegistroAuditoriaEntidad;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.ResultActions;

class ParcelaControladorIT extends ParcelaPruebaBase {

    @Autowired
    private ObjectMapper mapeador;

    @Autowired
    private RegistroAuditoriaSpringData auditoria;

    private ResultActions crear(String cuerpo, String rol) throws Exception {
        return mockMvc.perform(post(RUTA).with(conRol(rol))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpo));
    }

    private JsonNode crearValida(String nombre, String superficie) throws Exception {
        String respuesta = crear(cuerpo(nombre, superficie), "administrador")
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return mapeador.readTree(respuesta);
    }

    private ResultActions modificar(String id, String cuerpo, String rol) throws Exception {
        return mockMvc.perform(put(RUTA + "/" + id).with(conRol(rol))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpo));
    }

    private void verificarAuditoria(String id, String accion, String actor) {
        assertThat(auditoria.findAll())
                .filteredOn(registro -> registro.getIdEntidad().equals(UUID.fromString(id)))
                .filteredOn(registro -> registro.getAccion().equals(accion))
                .hasSize(1)
                .first()
                .satisfies((RegistroAuditoriaEntidad registro) -> {
                    assertThat(registro.getActor()).isEqualTo(actor);
                    assertThat(registro.getEntidad()).isEqualTo("PARCELA");
                    assertThat(registro.getFecha()).isNotNull();
                });
    }

    // Historia 1

    @Test
    void administradorRegistraUnaParcela() throws Exception {
        String respuesta = crear("{\"nombre\": \"Lote Norte\", \"superficieHectareas\": \"25.5\", "
                + "\"ubicacion\": \"Km 12, camino a Warnes\", \"descripcion\": \"Suelo arcilloso\"}", "administrador")
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", containsString("/api/gestion/v1/parcelas/")))
                .andExpect(jsonPath("$.id").isNotEmpty())
                .andExpect(jsonPath("$.nombre").value("Lote Norte"))
                .andExpect(jsonPath("$.superficieHectareas").value("25.5000"))
                .andExpect(jsonPath("$.ubicacion").value("Km 12, camino a Warnes"))
                .andExpect(jsonPath("$.descripcion").value("Suelo arcilloso"))
                .andExpect(jsonPath("$.version").value(0))
                .andExpect(jsonPath("$.fechaCreacion").isNotEmpty())
                .andExpect(jsonPath("$.fechaActualizacion").isNotEmpty())
                .andReturn().getResponse().getContentAsString();

        verificarAuditoria(mapeador.readTree(respuesta).get("id").asText(), "CREAR", "usuario-administrador");
    }

    @ParameterizedTest
    @ValueSource(strings = {"0", "-3.5"})
    void superficieCeroONegativaSeRechazaSinCrearNada(String superficie) throws Exception {
        crear(cuerpo("Lote Norte", superficie), "administrador")
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.codigo").value("SUPERFICIE_INVALIDA"));
        assertThat(parcelas.count()).isZero();
    }

    @Test
    void nombreRepetidoSinDistinguirMayusculasSeRechaza() throws Exception {
        crearValida("Lote Norte", "25.5");

        crear(cuerpo("lote norte", "10"), "administrador")
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.codigo").value("NOMBRE_PARCELA_DUPLICADO"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"gerencia", "tecnico_campo", "lectura_gestion"})
    void soloElAdministradorPuedeRegistrar(String rol) throws Exception {
        crear(cuerpo("Lote Norte", "25.5"), rol)
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.codigo").value("SIN_PERMISO"));
    }

    // Historia 2

    @Test
    void listadoSinParametrosDevuelveLasPrimeras20OrdenadasPorNombre() throws Exception {
        for (int i = 0; i < 30; i++) {
            crearValida("Lote %02d".formatted(29 - i), "1");
        }

        mockMvc.perform(get(RUTA).with(conRol("gerencia")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(20)))
                .andExpect(jsonPath("$.items[0].nombre").value("Lote 00"))
                .andExpect(jsonPath("$.items[19].nombre").value("Lote 19"))
                .andExpect(jsonPath("$.pagina").value(0))
                .andExpect(jsonPath("$.tamanio").value(20))
                .andExpect(jsonPath("$.total").value(30));
    }

    @Test
    void filtraPorTextoSinDistinguirMayusculas() throws Exception {
        crearValida("Lote Norte", "1");
        crearValida("Lote Sur", "1");

        mockMvc.perform(get(RUTA + "?nombre=norte").with(conRol("administrador")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].nombre").value("Lote Norte"))
                .andExpect(jsonPath("$.total").value(1));
    }

    @Test
    void paginacionInvalidaResponde400() throws Exception {
        mockMvc.perform(get(RUTA + "?tamanio=101").with(conRol("administrador")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"));
    }

    @Test
    void idInexistenteResponde404() throws Exception {
        mockMvc.perform(get(RUTA + "/" + UUID.randomUUID()).with(conRol("administrador")))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.codigo").value("PARCELA_NO_ENCONTRADA"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"administrador", "gerencia", "tecnico_campo", "lectura_gestion"})
    void losRolesDeLecturaVenListadoYDetalle(String rol) throws Exception {
        JsonNode parcela = crearValida("Lote Norte", "25.5");

        mockMvc.perform(get(RUTA).with(conRol(rol)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].superficieHectareas").value("25.5000"));
        mockMvc.perform(get(RUTA + "/" + parcela.get("id").asText()).with(conRol(rol)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nombre").value("Lote Norte"))
                .andExpect(jsonPath("$.superficieHectareas").value("25.5000"));
    }

    @Test
    void estadoCampaniaNoPuedeLeerParcelas() throws Exception {
        mockMvc.perform(get(RUTA).with(conRol("estado_campania")))
                .andExpect(status().isForbidden());
    }

    // Historia 3

    @Test
    void administradorModificaUnaParcelaYQuedaAuditada() throws Exception {
        JsonNode parcela = crearValida("Lote Norte", "25.5");
        String id = parcela.get("id").asText();

        modificar(id, cuerpoConVersion("Lote Norte", "27", 0), "administrador")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.superficieHectareas").value("27.0000"))
                .andExpect(jsonPath("$.version").value(1));

        mockMvc.perform(get(RUTA + "/" + id).with(conRol("gerencia")))
                .andExpect(jsonPath("$.superficieHectareas").value("27.0000"))
                .andExpect(jsonPath("$.fechaCreacion").value(parcela.get("fechaCreacion").asText()));
        verificarAuditoria(id, "MODIFICAR", "usuario-administrador");
    }

    @Test
    void nombreDeOtraParcelaSeRechazaAlModificar() throws Exception {
        crearValida("Lote Norte", "1");
        JsonNode sur = crearValida("Lote Sur", "1");

        modificar(sur.get("id").asText(), cuerpoConVersion("LOTE NORTE", "1", 0), "administrador")
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.codigo").value("NOMBRE_PARCELA_DUPLICADO"));
    }

    @Test
    void puedeConservarSuPropioNombre() throws Exception {
        JsonNode parcela = crearValida("Lote Norte", "1");

        modificar(parcela.get("id").asText(), cuerpoConVersion("LOTE NORTE", "1", 0), "administrador")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nombre").value("LOTE NORTE"));
    }

    @Test
    void versionDesactualizadaResponde409() throws Exception {
        JsonNode parcela = crearValida("Lote Norte", "1");
        String id = parcela.get("id").asText();
        modificar(id, cuerpoConVersion("Lote Norte", "2", 0), "administrador").andExpect(status().isOk());

        modificar(id, cuerpoConVersion("Lote Norte", "3", 0), "administrador")
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.codigo").value("CONFLICTO_CONCURRENCIA"));
    }

    @Test
    void modificarConDatosInvalidosOSinPermiso() throws Exception {
        String id = crearValida("Lote Norte", "1").get("id").asText();

        modificar(id, cuerpo("Lote Norte", "2"), "administrador")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.detalles[0].campo").value("version"));
        modificar(id, cuerpoConVersion("Lote Norte", "0", 0), "administrador")
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.codigo").value("SUPERFICIE_INVALIDA"));
        modificar(UUID.randomUUID().toString(), cuerpoConVersion("Otro", "2", 0), "administrador")
                .andExpect(status().isNotFound());
        modificar(id, cuerpoConVersion("Lote Norte", "2", 0), "gerencia")
                .andExpect(status().isForbidden());
    }

    // Casos borde de formato

    @ParameterizedTest
    @ValueSource(strings = {
            "{\"nombre\": \"Lote\", \"superficieHectareas\": \"10.12345\"}",
            "{\"nombre\": \"Lote\", \"superficieHectareas\": \"abc\"}",
            "{\"nombre\": \"Lote\", \"superficieHectareas\": 10.5}",
            "{\"nombre\": \"Lote\"}",
            "{\"superficieHectareas\": \"10\"}",
            "{\"nombre\": \"   \", \"superficieHectareas\": \"10\"}"
    })
    void formatoInvalidoResponde400(String cuerpo) throws Exception {
        crear(cuerpo, "administrador")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"))
                .andExpect(jsonPath("$.detalles[0].campo").isNotEmpty());
        assertThat(parcelas.count()).isZero();
    }

    @Test
    void recortaElNombreAntesDeValidarUnicidadYLongitud() throws Exception {
        String cienCaracteres = "a".repeat(100);

        crear(cuerpo("   " + cienCaracteres + "   ", "1"), "administrador")
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.nombre").value(cienCaracteres));
        crear(cuerpo(cienCaracteres, "1"), "administrador")
                .andExpect(status().isConflict());
        crear(cuerpo("b".repeat(101), "1"), "administrador")
                .andExpect(status().isBadRequest());
    }

    @Test
    void idConFormatoInvalidoResponde400() throws Exception {
        mockMvc.perform(get(RUTA + "/no-es-uuid").with(conRol("administrador")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"));
    }

    // OpenAPI

    @Test
    void openApiListaLosEndpointsConSusErrores() throws Exception {
        String documento = mockMvc.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        JsonNode rutas = mapeador.readTree(documento).get("paths");
        JsonNode coleccion = rutas.get(RUTA);
        JsonNode detalle = rutas.get(RUTA + "/{id}");

        assertThat(coleccion.get("post").get("responses").get("409").get("description").asText())
                .isEqualTo("NOMBRE_PARCELA_DUPLICADO");
        assertThat(coleccion.get("post").get("responses").get("422").get("description").asText())
                .isEqualTo("SUPERFICIE_INVALIDA");
        assertThat(coleccion.get("get").get("responses").has("400")).isTrue();
        assertThat(detalle.get("get").get("responses").get("404").get("description").asText())
                .isEqualTo("PARCELA_NO_ENCONTRADA");
        assertThat(detalle.get("put").get("responses").get("409").get("description").asText())
                .contains("CONFLICTO_CONCURRENCIA");
    }
}
