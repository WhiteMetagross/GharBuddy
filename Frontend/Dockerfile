FROM node:20-alpine

WORKDIR /app

# Copy dependency configs
COPY package.json package-lock.json ./
RUN npm install

# Copy source
COPY . .

# Build code bundle
RUN npm run build

EXPOSE 5173

# Execute Vite with external host bindings enabled
CMD ["npm", "run", "dev", "--", "--host"]
