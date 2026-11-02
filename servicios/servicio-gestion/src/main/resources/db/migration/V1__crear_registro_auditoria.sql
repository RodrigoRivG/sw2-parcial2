CREATE TABLE registro_auditoria (
    id              UUID PRIMARY KEY,
    actor           VARCHAR(100) NOT NULL,
    accion          VARCHAR(50)  NOT NULL,
    entidad         VARCHAR(50)  NOT NULL,
    id_entidad      UUID         NOT NULL,
    id_correlacion  VARCHAR(64),
    fecha           TIMESTAMPTZ  NOT NULL
);
CREATE INDEX ix_auditoria_entidad ON registro_auditoria (entidad, id_entidad);
