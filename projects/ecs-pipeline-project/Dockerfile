FROM node:20-alpine AS base

WORKDIR /usr/src/app

COPY app/package.json ./
RUN npm install --production

COPY app/ ./

ARG APP_VERSION=unset
ENV APP_VERSION=$APP_VERSION
ENV PORT=3000

EXPOSE 3000

# Basic container-level healthcheck (in addition to ECS/ALB target health checks)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -qO- http://localhost:3000/health || exit 1

CMD ["node", "index.js"]
