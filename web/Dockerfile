# 빌드 컨텍스트 = web/ 디렉터리.  (docker build -t nl2order-web ./web)
# 데이터는 web/data/ 를 사용한다 — 빌드 전에 `npm run sync-data` 로 ../smoke 에서 복사해 두면 컨테이너가 ../smoke 에 의존하지 않는다.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
COPY shared ./shared
COPY scripts ./scripts
COPY public ./public
COPY data ./data
# ../smoke 가 컨텍스트에 없으므로 sync-data 는 "원본 없음 → 기존 data/ 사용" 으로 조용히 넘어간다
RUN npm run build && npm run sync-data

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production PORT=3000 SMOKE_DIR=./data
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev
COPY --from=build /app/dist ./dist
COPY --from=build /app/shared ./shared
COPY --from=build /app/public ./public
COPY --from=build /app/data ./data
EXPOSE 3000
CMD ["node", "dist/server.js"]
