# Stage 1: build the static files with Node.
FROM node:20-alpine AS build
WORKDIR /build
# npm ci installs exactly what package-lock.json says (reproducible builds).
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
# Vite outputs plain HTML/CSS/JS into /build/dist - no Node needed to serve it.

# Stage 2: serve those static files with nginx (small, fast).
FROM nginx:alpine
COPY --from=build /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
