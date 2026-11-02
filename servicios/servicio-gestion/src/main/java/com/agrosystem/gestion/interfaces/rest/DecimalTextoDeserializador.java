package com.agrosystem.gestion.interfaces.rest;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.deser.std.StdScalarDeserializer;
import java.io.IOException;
import java.math.BigDecimal;
import java.util.regex.Pattern;
import org.springframework.boot.jackson.JsonComponent;

/** La constitución exige decimales como texto: rechaza números JSON y notación científica. */
@JsonComponent
public class DecimalTextoDeserializador extends StdScalarDeserializer<BigDecimal> {

    private static final Pattern FORMATO_DECIMAL = Pattern.compile("-?\\d+(\\.\\d+)?");

    public DecimalTextoDeserializador() {
        super(BigDecimal.class);
    }

    @Override
    public BigDecimal deserialize(JsonParser parser, DeserializationContext contexto) throws IOException {
        if (!parser.hasToken(JsonToken.VALUE_STRING)) {
            return (BigDecimal) contexto.handleUnexpectedToken(BigDecimal.class, parser);
        }
        String texto = parser.getText().trim();
        if (!FORMATO_DECIMAL.matcher(texto).matches()) {
            return (BigDecimal) contexto.handleWeirdStringValue(BigDecimal.class, texto, "no es un decimal válido");
        }
        return new BigDecimal(texto);
    }
}
