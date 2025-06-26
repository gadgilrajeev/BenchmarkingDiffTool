#!/bin/bash

echo "🧹 Stopping and cleaning up existing containers, volumes, and orphans..."
sudo docker-compose down --volumes --remove-orphans

echo "🗑️ Pruning unused Docker images, containers, networks, and volumes..."
sudo docker system prune -a --volumes -f

echo "🔨 Rebuilding Docker images without cache..."
sudo docker-compose build --no-cache

echo "🚀 Starting Docker containers..."
sudo docker-compose up
