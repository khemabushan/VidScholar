# ============================================================
# VidScholar Frontend - Dockerfile
# ============================================================
# Multi-stage build: install deps + build the static bundle in a
# Node stage, then serve it with Vite's preview server. For a true
# production deployment, swap the final stage for nginx serving the
# /app/dist folder instead — kept as Vite preview here for simplicity
# and to match local dev behavior exactly.

FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM node:20-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production

COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/vite.config.ts ./

EXPOSE 5173

CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "5173"]
