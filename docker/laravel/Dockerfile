# Imagen de desarrollo para servicio-operaciones (Laravel).
# El código se monta en /app.
FROM php:8.4-cli

# zip: Composer · bcmath: cálculos · sockets: RabbitMQ (php-amqplib) · pcntl: workers
RUN apt-get update \
    && apt-get install -y --no-install-recommends git unzip libzip-dev \
    && docker-php-ext-install zip bcmath sockets pcntl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

# Usuario con UID 1000 (el mismo que tu usuario de Ubuntu)
RUN useradd -m -u 1000 dev
ENV COMPOSER_HOME=/tmp/composer

USER dev
WORKDIR /app

EXPOSE 8000
CMD ["sh", "-c", "composer install --no-interaction && php artisan serve --host=0.0.0.0 --port=8000"]
