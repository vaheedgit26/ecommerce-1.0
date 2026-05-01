# Build stage
FROM node:18-alpine as build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build

# Serve with nginx
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html

# 👇 ENV (React needs ENV)
ENV REACT_APP_USER_POOL_ID
ENV REACT_APP_CLIENT_ID
ENV REACT_APP_API_BASE_URL

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
