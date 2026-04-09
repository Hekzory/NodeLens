# syntax=docker/dockerfile:1
FROM node:25-alpine AS builder

RUN npm install -g pnpm@10

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Pre-compress static assets with brotli and gzip
RUN apk add --no-cache brotli gzip \
 && find /app/dist -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' -o -name '*.svg' -o -name '*.json' \) \
      -exec brotli -k -q 11 {} \; \
      -exec gzip -k -9 {} \;

# Build nginx brotli module matching the runtime nginx version
FROM nginx:alpine AS brotli-build
RUN apk add --no-cache git gcc g++ make pcre2-dev zlib-dev brotli-dev linux-headers \
 && NGINX_VER=$(nginx -v 2>&1 | sed 's|.*/||') \
 && wget -qO- "https://nginx.org/download/nginx-${NGINX_VER}.tar.gz" | tar xz \
 && git clone --recurse-submodules https://github.com/google/ngx_brotli /tmp/ngx_brotli \
 && cd "nginx-${NGINX_VER}" \
 && ./configure --with-compat --add-dynamic-module=/tmp/ngx_brotli \
 && make modules \
 && cp objs/ngx_http_brotli_static_module.so objs/ngx_http_brotli_filter_module.so /tmp/

FROM nginx:alpine
# Load brotli modules (filter = dynamic compression, static = pre-compressed files)
COPY --from=brotli-build /tmp/ngx_http_brotli_filter_module.so \
                          /tmp/ngx_http_brotli_static_module.so \
                          /usr/lib/nginx/modules/
RUN apk add --no-cache brotli-libs \
 && sed -i '1i load_module /usr/lib/nginx/modules/ngx_http_brotli_static_module.so;\nload_module /usr/lib/nginx/modules/ngx_http_brotli_filter_module.so;' /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
