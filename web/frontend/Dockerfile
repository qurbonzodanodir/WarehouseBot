FROM node:20-alpine

WORKDIR /app

# Install dependencies first (for caching)
COPY package.json package-lock.json* ./
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
