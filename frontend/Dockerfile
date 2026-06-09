# CRC React app — build with Node, serve static build via nginx (SPA routing).
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json yarn.lock* ./
RUN yarn install --network-timeout 600000

COPY . .

ARG REACT_APP_BACKEND_URL=""
ARG REACT_APP_CRC_SITE="true"
ARG REACT_APP_CARIB_SITE_URL="https://carib-recon.org"
ARG REACT_APP_LOGIN_URL="https://carib-recon.org/login"
ARG REACT_APP_GANTT_APP_URL="https://carib-recon.org/gantt"
ARG GENERATE_SOURCEMAP="false"
ARG CI="true"

ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL \
    REACT_APP_CRC_SITE=$REACT_APP_CRC_SITE \
    REACT_APP_CARIB_SITE_URL=$REACT_APP_CARIB_SITE_URL \
    REACT_APP_LOGIN_URL=$REACT_APP_LOGIN_URL \
    REACT_APP_GANTT_APP_URL=$REACT_APP_GANTT_APP_URL \
    GENERATE_SOURCEMAP=$GENERATE_SOURCEMAP \
    CI=$CI

RUN yarn build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
