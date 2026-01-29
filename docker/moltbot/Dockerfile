# Moltbot Docker Image for PISAMA Testing
FROM node:22-alpine

# Install pnpm
RUN npm install -g pnpm@latest

# Install Moltbot globally
RUN pnpm add -g moltbot@latest

# Create config directory
RUN mkdir -p /root/.clawdbot

# Set working directory
WORKDIR /app

# Expose gateway port
EXPOSE 18789

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD wget -q --spider http://127.0.0.1:18789/ || exit 1

# Default command - run gateway
CMD ["moltbot", "gateway", "--port", "18789", "--host", "0.0.0.0"]
