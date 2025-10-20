# Dockerfile for the ApexInvest Advisor frontend
#
# This multi‑stage build compiles the React application and then serves
# the static files via Nginx.  Using Nginx allows us to run the
# frontend as a lightweight container with robust HTTP serving.

FROM node:18-alpine AS build
WORKDIR /app
COPY package.json package.json
COPY tailwind.config.js tailwind.config.js
COPY public public
COPY src src

RUN npm install && npm run build

FROM nginx:1.25-alpine
COPY --from=build /app/build /usr/share/nginx/html
# Copy a minimal Nginx config if you need to set custom headers or
# compression.  For simplicity we use the default configuration.
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]