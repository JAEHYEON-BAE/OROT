# syntax=docker/dockerfile:1

# ─── 의존성 (dev·prod 공유) ──────────────────────────────────────
# devDependencies 도 설치한다 — prod 단계의 `next build` 가 typescript·tailwind 를 쓴다.
FROM node:22-alpine AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

# ─── 개발 ────────────────────────────────────────────────────────
# 소스는 compose 가 마운트한다. COPY 는 마운트되지 않는 파일(설정 등)을 위해 남긴다.
FROM deps AS dev
ENV NODE_ENV=development
COPY apps/web ./
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ─── 운영 ────────────────────────────────────────────────────────
# **이미지 안에서 빌드한다.** 개발 서버(`next dev`)를 그대로 상시 운영에 쓰면
# 매 요청마다 컴파일해 느리고, 소스맵과 개발 오버레이가 외부에 노출된다.
FROM deps AS prod
ENV NODE_ENV=production
COPY apps/web ./
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
