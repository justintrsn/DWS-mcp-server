# PostgreSQL Dockerfile with Anime Database
FROM postgres:15

# Set environment variables
ENV POSTGRES_DB=test_footfall
ENV POSTGRES_USER=test_user
ENV POSTGRES_PASSWORD=test_pass

# Copy SQL initialization script
COPY scripts/setup_anime_db.sql /docker-entrypoint-initdb.d/01-anime.sql

# Set correct permissions for initialization script
RUN chmod +x /docker-entrypoint-initdb.d/01-anime.sql

# Expose PostgreSQL port
EXPOSE 5432

# Use default postgres entrypoint