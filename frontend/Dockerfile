# 构建阶段
FROM node:20-alpine AS build
WORKDIR /app
ARG NPM_REGISTRY=https://registry.npmmirror.com
COPY package.json package-lock.json ./
RUN npm ci --registry="$NPM_REGISTRY" --fetch-retries=1 --fetch-timeout=30000 --no-audit --no-fund && test -x node_modules/.bin/tsc
COPY . .
RUN npm run build

# 运行阶段：nginx 托管静态资源并反向代理 /api
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=12 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
