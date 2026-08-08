FROM node:20-alpine

WORKDIR /app

# Install dependencies first
COPY package*.json ./
RUN npm install

# Copy application files
COPY . .

# Build-time argument for Next.js API URL
ARG NEXT_PUBLIC_API_URL="http://localhost:8000/api/v1"
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Build the static Next.js assets
RUN npm run build

# Expose port
EXPOSE 3000

# Start Next.js server
CMD ["npm", "run", "start"]
