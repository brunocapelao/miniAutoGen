# Stage 1: Build console (Node.js)
FROM node:18-alpine AS console-builder
WORKDIR /build/console
COPY console/package*.json ./
RUN npm ci
COPY console/ ./
# Next.js standalone output for minimal Docker image
RUN npm run build

# Stage 2: Python runtime
FROM python:3.13-slim
WORKDIR /app

# Install miniautogen
COPY pyproject.toml README.md ./
COPY miniautogen/ miniautogen/
RUN pip install --no-cache-dir .

# Copy built console assets
# NOTE: Adjust paths if the Next.js build output structure differs
COPY --from=console-builder /build/console/.next/standalone ./miniautogen/server/static/
COPY --from=console-builder /build/console/.next/static ./miniautogen/server/static/_next/static/
COPY --from=console-builder /build/console/public ./miniautogen/server/static/public/

# Non-root user for security
RUN useradd -m miniautogen
USER miniautogen

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/workspace')" || exit 1

ENTRYPOINT ["miniautogen"]
CMD ["console", "--host", "0.0.0.0"]
