# syntax=docker/dockerfile:1
FROM maven:3.9-eclipse-temurin-21 AS construccion
WORKDIR /fuente
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q package -DskipTests

FROM eclipse-temurin:21-jre
RUN useradd --system --uid 1001 servicio
COPY --from=construccion /fuente/target/api-gateway-*.jar /app/api-gateway.jar
USER servicio
ENTRYPOINT ["java", "-jar", "/app/api-gateway.jar"]
