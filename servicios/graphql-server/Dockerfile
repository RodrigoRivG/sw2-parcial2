# syntax=docker/dockerfile:1
FROM node:24-alpine AS construccion
WORKDIR /fuente
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json tsconfig.build.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev

FROM node:24-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY --from=construccion /fuente/package.json ./
COPY --from=construccion /fuente/node_modules ./node_modules
COPY --from=construccion /fuente/dist ./dist
USER node
EXPOSE 4000
CMD ["node", "dist/main.js"]
