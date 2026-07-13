# Imagen para correr Sendy (app PHP licenciada) en el VPS detrás de Traefik.
# El código de Sendy NO vive aquí (es licenciado): se monta desde ./app, que
# se sube por scp desde la instalación de SiteGround. Ver README.md.
FROM php:8.2-apache

# Extensiones que Sendy requiere: mysqli (DB), gd (imágenes de campañas),
# curl/openssl (SES + verificación de licencia), mbstring, zip, intl.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpng-dev libjpeg-dev libfreetype6-dev libzip-dev libicu-dev libonig-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j"$(nproc)" mysqli gd zip intl \
    && a2enmod rewrite \
    && rm -rf /var/lib/apt/lists/*

# Sendy manda correos grandes y sube listas por CSV: subir límites de PHP.
RUN { \
      echo "upload_max_filesize = 64M"; \
      echo "post_max_size = 64M"; \
      echo "memory_limit = 256M"; \
      echo "max_execution_time = 120"; \
    } > /usr/local/etc/php/conf.d/sendy.ini

# Apache sirve /var/www/html (montado como volumen desde ./app).
WORKDIR /var/www/html
