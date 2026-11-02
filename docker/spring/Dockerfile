# syntax=docker/dockerfile:1
# Imagen de desarrollo compartida por servicio-gestion y api-gateway.
# El código NO se copia: se monta como volumen en /app.
FROM eclipse-temurin:21-jdk

RUN apt-get update \
    && apt-get install -y --no-install-recommends inotify-tools curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Maven (para no depender del wrapper durante el desarrollo)
ARG MAVEN_VERSION=3.9.11
RUN curl -fsSL "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz" \
      | tar -xz -C /opt \
    && ln -s "/opt/apache-maven-${MAVEN_VERSION}/bin/mvn" /usr/local/bin/mvn

# Usuario con UID 1000 (el mismo que tu usuario de Ubuntu) para que los
# archivos generados no queden a nombre de root.
RUN if ! id -u 1000 >/dev/null 2>&1; then useradd -m -u 1000 dev; fi \
    && mkdir -p /cache/m2 && chown -R 1000:1000 /cache

# Caché de Maven en un volumen: las dependencias se descargan una sola vez
ENV MAVEN_OPTS="-Dmaven.repo.local=/cache/m2/repository"

# Script de arranque con recarga en caliente:
# recompila al guardar y DevTools reinicia la app.
COPY --chmod=755 <<'EOF' /usr/local/bin/spring-dev
#!/bin/sh
set -e
cd /app
mvn -q -B compile
(
  while inotifywait -qq -r -e close_write,create,delete,move src/main; do
    mvn -q -B -o compile || echo "[spring-dev] Error de compilación: corrige y vuelve a guardar"
  done
) &
exec mvn -B spring-boot:run \
  -Dspring-boot.run.jvmArguments="-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005"
EOF

USER 1000
WORKDIR /app
CMD ["spring-dev"]
