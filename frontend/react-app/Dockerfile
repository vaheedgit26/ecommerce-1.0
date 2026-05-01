# Build stage
FROM node:18-alpine as build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Serve with nginx
FROM nginx:alpine

# Install envsubst
RUN apk add --no-cache gettext

# Copy React build
COPY --from=build /app/build /usr/share/nginx/html

# Copy config template + entrypoint
COPY config.template.js /usr/share/nginx/html/config.template.js
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 80

CMD ["/entrypoint.sh"]
