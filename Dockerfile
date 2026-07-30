# AquaMind AI — frontend + Express reverse proxy
# Multi-stage build: compile the Vite SPA and the esbuild-bundled server,
# then run the production bundle under a minimal Node runtime.

FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json

# The FastAPI backend is a separate service (see docker-compose.yml).
# FASTAPI_INTERNAL_URL tells this container's /api/* proxy where to send
# requests — defaults to the compose service name "fastapi:8000".
ENV FASTAPI_INTERNAL_URL=http://fastapi:8000
ENV PORT=3000
EXPOSE 3000

CMD ["node", "dist/server.cjs"]
