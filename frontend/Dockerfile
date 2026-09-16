# Development stage
FROM node:22-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# Production build stage
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production serve stage
FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
# SPA routing config
RUN echo "server { listen 80; location / { root /usr/share/nginx/html; index index.html index.htm; try_files `$uri `$uri/ /index.html; } location /api/ { proxy_pass http://backend:8010; } }" > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]