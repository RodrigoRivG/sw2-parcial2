package com.agrosystem.gestion.interfaces.messaging;

import com.agrosystem.gestion.application.campaign.AnularCostoSagaCasoUso;
import com.agrosystem.gestion.application.campaign.ComandoAnularCosto;
import com.agrosystem.gestion.application.campaign.ComandoRegistrarCosto;
import com.agrosystem.gestion.application.campaign.RegistrarCostoSagaCasoUso;
import com.agrosystem.gestion.application.campaign.RespuestaSaga;
import com.agrosystem.gestion.application.port.PublicadorMensajes;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;
import java.util.Optional;
import java.util.UUID;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

/**
 * Un solo consumidor para ambos comandos, porque comparten cola. Publica la respuesta después del commit;
 * si falla, el mensaje se reintenta y, por idempotencia, solo se vuelve a publicar.
 */
@Component
public class ConsumidorComandosSaga {

    private static final Logger LOG = LoggerFactory.getLogger(ConsumidorComandosSaga.class);
    private static final String REGISTRAR = "RegistrarCostoCampania";
    private static final String ANULAR = "AnularCostoCampania";
    private static final String DATOS_INVALIDOS = "DATOS_INVALIDOS";
    private static final String CLAVE_MDC = "idCorrelacion";
    private static final int VERSION_SOPORTADA = 1;
    private static final int LARGO_MAXIMO_CORRELACION = 64;
    private static final Pattern FORMATO_MONTO = Pattern.compile("\\d{1,12}(\\.\\d{1,2})?");

    private final RegistrarCostoSagaCasoUso registrar;
    private final AnularCostoSagaCasoUso anular;
    private final PublicadorMensajes publicador;
    private final ObjectMapper mapeador;

    public ConsumidorComandosSaga(
            RegistrarCostoSagaCasoUso registrar,
            AnularCostoSagaCasoUso anular,
            PublicadorMensajes publicador,
            ObjectMapper mapeador) {
        this.registrar = registrar;
        this.anular = anular;
        this.publicador = publicador;
        this.mapeador = mapeador;
    }

    @RabbitListener(queues = "${gestion.saga.cola-comandos}")
    public void recibir(Message mensaje) {
        Optional<SobreMensaje> interpretado = SobreMensaje.interpretar(mensaje.getBody(), mapeador);
        if (interpretado.isEmpty() || !esTipoConocido(interpretado.get().tipo())) {
            LOG.error("Mensaje no interpretable: se envía a la Dead Letter Queue sin reintentos");
            publicador.enviarAColaDeErrores(mensaje.getBody());
            return;
        }
        SobreMensaje sobre = interpretado.get();
        if (sobre.idCorrelacion().length() <= LARGO_MAXIMO_CORRELACION) {
            MDC.put(CLAVE_MDC, sobre.idCorrelacion());
        }
        try {
            RespuestaSaga respuesta = REGISTRAR.equals(sobre.tipo()) ? procesarRegistro(sobre) : procesarAnulacion(sobre);
            publicador.publicarRespuestaSaga(respuesta.tipo(), sobre.idCorrelacion(), respuesta.datos());
            LOG.info("Mensaje {} de tipo {} procesado con resultado {}", sobre.idMensaje(), sobre.tipo(), respuesta.tipo());
        } finally {
            MDC.remove(CLAVE_MDC);
        }
    }

    private boolean esTipoConocido(String tipo) {
        return REGISTRAR.equals(tipo) || ANULAR.equals(tipo);
    }

    private RespuestaSaga procesarRegistro(SobreMensaje sobre) {
        JsonNode datos = sobre.datos();
        UUID idSaga = uuid(datos.path("idSaga"));
        UUID idLabor = uuid(datos.path("idLabor"));
        UUID idCampania = uuid(datos.path("idCampania"));
        Optional<LocalDate> fecha = fechaOcurrencia(sobre);
        JsonNode monto = datos.path("monto");
        boolean valido = sobreValido(sobre, idSaga)
                && idLabor != null
                && idCampania != null
                && fecha.isPresent()
                && montoValido(monto)
                && "INSUMO".equals(datos.path("categoria").asText());
        if (!valido) {
            return RespuestaSaga.rechazado(
                    texto(datos, "idSaga"), texto(datos, "idLabor"), texto(datos, "idCampania"),
                    DATOS_INVALIDOS, "Los datos del comando no son válidos.");
        }
        return registrar.ejecutar(new ComandoRegistrarCosto(
                sobre.idMensaje(), idSaga, idLabor, idCampania, new BigDecimal(monto.asText()), fecha.get(),
                sobre.origen().asText()));
    }

    private RespuestaSaga procesarAnulacion(SobreMensaje sobre) {
        JsonNode datos = sobre.datos();
        UUID idSaga = uuid(datos.path("idSaga"));
        UUID idLabor = uuid(datos.path("idLabor"));
        UUID idCampania = uuid(datos.path("idCampania"));
        if (!sobreValido(sobre, idSaga) || idLabor == null || idCampania == null) {
            return RespuestaSaga.anulacionRechazada(
                    texto(datos, "idSaga"), texto(datos, "idLabor"), texto(datos, "idCampania"), null,
                    DATOS_INVALIDOS, "Los datos del comando no son válidos.");
        }
        return anular.ejecutar(new ComandoAnularCosto(
                sobre.idMensaje(), idSaga, idLabor, idCampania, sobre.origen().asText()));
    }

    private boolean sobreValido(SobreMensaje sobre, UUID idSaga) {
        return idSaga != null
                && sobre.idCorrelacion().equalsIgnoreCase(idSaga.toString())
                && sobre.version().isInt()
                && sobre.version().asInt() == VERSION_SOPORTADA
                && sobre.origen().isTextual()
                && !sobre.origen().asText().isBlank();
    }

    /** Solo texto decimal mayor a 0: la convención común prohíbe los montos como número JSON. */
    private boolean montoValido(JsonNode monto) {
        return monto.isTextual()
                && FORMATO_MONTO.matcher(monto.asText()).matches()
                && new BigDecimal(monto.asText()).signum() > 0;
    }

    private Optional<LocalDate> fechaOcurrencia(SobreMensaje sobre) {
        try {
            return Optional.of(Instant.parse(sobre.fechaOcurrencia().asText()).atOffset(ZoneOffset.UTC).toLocalDate());
        } catch (DateTimeParseException error) {
            return Optional.empty();
        }
    }

    private UUID uuid(JsonNode valor) {
        if (!valor.isTextual()) {
            return null;
        }
        try {
            return UUID.fromString(valor.asText());
        } catch (IllegalArgumentException error) {
            return null;
        }
    }

    private String texto(JsonNode datos, String campo) {
        JsonNode valor = datos.path(campo);
        return valor.isTextual() ? valor.asText() : null;
    }
}
