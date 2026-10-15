# syntax=docker/dockerfile:1
#
# Frontend de production : build Vite (Node, étape jetée) puis fichiers statiques servis par Caddy,
# qui relaie aussi /api vers l'API — même origine, exigée par la vérification d'origine CSRF et les
# cookies de session (secure, SameSite=Lax). Contexte de construction : frontend/.
#
#   docker build -t greenfinance-frontend frontend

FROM node:24-alpine AS construction
WORKDIR /app
# .npmrc avec le verrou : legacy-peer-deps (peer react@^18 de @tremor/react), sans quoi npm ci échoue.
COPY package.json package-lock.json .npmrc ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

FROM caddy:2.11-alpine
COPY --from=construction /app/dist /srv
# La configuration (deploy/Caddyfile) est montée par docker-compose.prod.yml.
