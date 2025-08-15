# Multi-stage build for Virtual Requirements Buddy (VRB)
# Stage 1: Dependencies
FROM python:3.12.3-slim as deps

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install Poetry with a specific version for compatibility
RUN pip install "poetry>=2.0.0,<3.0.0"

# Configure Poetry to not create virtual environments (since we're in a container)
RUN poetry config virtualenvs.create false

# Set the working directory
WORKDIR /app

# Copy Poetry configuration files first for better caching
COPY pyproject.toml poetry.lock ./

# Install dependencies using Poetry (only main dependencies, no dev dependencies, no root project)
RUN poetry install --only main --no-interaction --no-root

# Stage 2: Runtime
FROM python:3.12.3-slim as runtime

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Copy Python packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy your application code into the container
COPY . /app/

# Expose the port
EXPOSE 8080

# Run the application
CMD ["python", "-m", "chainlit", "run", "app.py", "-h", "--port", "8080"]