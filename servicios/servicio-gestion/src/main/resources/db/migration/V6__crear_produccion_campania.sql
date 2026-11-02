CREATE TABLE produccion_campania (
    id_campania       UUID          PRIMARY KEY REFERENCES campania (id),
    cantidad          NUMERIC(14,2) NOT NULL CHECK (cantidad >= 0),
    unidad            VARCHAR(20)   NOT NULL CHECK (unidad IN ('KILOGRAMO')),
    fecha_cosecha     DATE          NOT NULL,
    observaciones     VARCHAR(500),
    fecha_registro    TIMESTAMPTZ   NOT NULL,
    usuario_registro  VARCHAR(100)  NOT NULL
);
