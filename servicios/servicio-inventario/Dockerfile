# syntax=docker/dockerfile:1
FROM node:24-alpine AS construccion
WORKDIR /fuente
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json tsconfig.build.json nest-cli.json ./
COPY src ./src
COPY migrations ./migrations
RUN npm run build && npm prune --omit=dev

FROM node:24-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY --from=construccion /fuente/package.json ./
COPY --from=construccion /fuente/node_modules ./node_modules
COPY --from=construccion /fuente/dist ./dist
USER node
CMD ["node", "dist/src/main"]
