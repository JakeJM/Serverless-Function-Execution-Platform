FROM node:18-alpine
WORKDIR /app
COPY package.json .
RUN npm install
CMD ["node", "handler.js"]
