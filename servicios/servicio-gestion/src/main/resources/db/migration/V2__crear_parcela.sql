CREATE TABLE parcela (
    id                    UUID PRIMARY KEY,
    nombre                VARCHAR(100)  NOT NULL,
    superficie_hectareas  NUMERIC(12,4) NOT NULL CHECK (superficie_hectareas > 0),
    ubicacion             VARCHAR(200),
    descripcion           VARCHAR(500),
    version               BIGINT        NOT NULL,
    fecha_creacion        TIMESTAMPTZ   NOT NULL,
    fecha_actualizacion   TIMESTAMPTZ   NOT NULL
);
CREATE UNIQUE INDEX ux_parcela_nombre ON parcela (lower(nombre));
