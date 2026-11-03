# syntax=docker/dockerfile:1
# Imagen del servicio (constitución §2: ECS con Fargate). La misma imagen corre la API (Apache),
# el programador (php artisan schedule:work) y el consumidor de la Saga, cambiando el comando.
FROM composer:2 AS dependencias
WORKDIR /fuente
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist --no-interaction --ignore-platform-reqs
COPY . .
RUN composer dump-autoload --no-dev --optimize --no-scripts

FROM php:8.4-apache
RUN docker-php-ext-install bcmath sockets pcntl \
    && a2enmod rewrite \
    && sed -ri 's!/var/www/html!/var/www/html/public!g; s!:80>!:8080>!' /etc/apache2/sites-available/000-default.conf \
    && sed -ri 's!^Listen 80$!Listen 8080!' /etc/apache2/ports.conf \
    && printf '<Directory /var/www/html/public>\n    AllowOverride All\n</Directory>\n' > /etc/apache2/conf-enabled/laravel.conf \
    && printf 'upload_max_filesize = 10M\npost_max_size = 40M\nmemory_limit = 256M\nexpose_php = Off\n' > /usr/local/etc/php/conf.d/limites.ini \
    && mv /usr/local/etc/php/php.ini-production /usr/local/etc/php/php.ini
WORKDIR /var/www/html
COPY --from=dependencias --chown=www-data:www-data /fuente ./
# storage/ no se versiona: Laravel escribe ahí la caché en archivo y los bloqueos del programador
RUN mkdir -p storage/framework/cache && chown -R www-data:www-data storage && php artisan package:discover --ansi
# Sin root: Apache escucha en 8080
USER www-data
EXPOSE 8080
