# FTC Predictor Local Development Makefile

.PHONY: help start stop restart logs clean setup sync-all sync-teams sync-events sync-matches counts shell

# Default target
help:
	@echo "FTC Predictor Local Development Commands:"
	@echo ""
	@echo "Database Management:"
	@echo "  start      - Start PostgreSQL and pgAdmin containers"
	@echo "  stop       - Stop all containers"
	@echo "  restart    - Restart all containers"
	@echo "  logs       - Show container logs"
	@echo "  clean      - Stop containers and remove volumes (WARNING: deletes data)"
	@echo ""
	@echo "Setup:"
	@echo "  setup      - Install Python dependencies and set up environment"
	@echo ""
	@echo "Data Sync:"
	@echo "  sync-all   - Sync all tables from DynamoDB"
	@echo "  sync-teams - Sync teams table only"
	@echo "  sync-events- Sync events table only"
	@echo "  sync-matches- Sync matches table only (large!)"
	@echo "  counts     - Show record counts comparison"
	@echo ""
	@echo "Database Access:"
	@echo "  shell      - Open PostgreSQL shell"
	@echo ""
	@echo "Examples:"
	@echo "  make start && make setup && make sync-all"
	@echo "  make sync-matches LIMIT=1000  # Sync with limit"

# Database Management
start:
	@echo "Starting FTC Predictor local database..."
	docker-compose up -d
	@echo "Waiting for database to be ready..."
	@sleep 10
	@echo "Database started!"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  pgAdmin:    http://localhost:8080"

stop:
	@echo "Stopping containers..."
	docker-compose down

restart:
	@echo "Restarting containers..."
	docker-compose restart

logs:
	docker-compose logs -f

clean:
	@echo "WARNING: This will delete all local data!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	docker-compose down -v
	docker system prune -f

# Setup
setup:
	@echo "Setting up local development environment..."
	pip install -r requirements.txt
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "Created .env file from template. Please edit with your values."; \
	fi
	@echo "Setup complete!"

# Data Sync Commands
sync-all:
	@echo "Syncing all tables from DynamoDB..."
	python sync_utils.py --action sync-all $(if $(LIMIT),--limit $(LIMIT))

sync-teams:
	@echo "Syncing teams table..."
	python sync_utils.py --action sync-teams $(if $(LIMIT),--limit $(LIMIT))

sync-events:
	@echo "Syncing events table..."
	python sync_utils.py --action sync-events $(if $(LIMIT),--limit $(LIMIT))

sync-matches:
	@echo "Syncing matches table..."
	python sync_utils.py --action sync-matches $(if $(LIMIT),--limit $(LIMIT))

counts:
	@echo "Checking record counts..."
	python sync_utils.py --action counts

# Database Access
shell:
	@echo "Opening PostgreSQL shell..."
	docker exec -it ftc-predictor-db psql -U ftc_dev -d ftc_predictor

# Development helpers
test-connection:
	@echo "Testing database connection..."
	@python -c "import psycopg2; conn = psycopg2.connect(host='localhost', database='ftc_predictor', user='ftc_dev', password='ftc_dev_password'); print('✓ PostgreSQL connection successful'); conn.close()"

check-aws:
	@echo "Checking AWS credentials..."
	@aws sts get-caller-identity

status:
	@echo "Container Status:"
	@docker-compose ps
	@echo ""
	@echo "Database Status:"
	@make test-connection 2>/dev/null || echo "✗ PostgreSQL connection failed"
	@echo ""
	@echo "Record Counts:"
	@make counts

# Quick development setup
dev-setup: start setup
	@echo "Waiting for database to be fully ready..."
	@sleep 15
	@echo "Running initial data sync (limited)..."
	@make sync-teams LIMIT=100
	@make sync-events LIMIT=50
	@echo ""
	@echo "Development environment ready!"
	@echo "Run 'make sync-all' to get full dataset (this may take a while)"

# Production sync (full data)
prod-sync:
	@echo "Starting full production data sync..."
	@echo "This may take 30+ minutes for the matches table..."
	@make sync-all

# Backup and restore (for future use)
backup:
	@echo "Creating database backup..."
	docker exec ftc-predictor-db pg_dump -U ftc_dev ftc_predictor > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup created: backup_$(shell date +%Y%m%d_%H%M%S).sql"

restore:
	@if [ -z "$(FILE)" ]; then echo "Usage: make restore FILE=backup_file.sql"; exit 1; fi
	@echo "Restoring from $(FILE)..."
	docker exec -i ftc-predictor-db psql -U ftc_dev ftc_predictor < $(FILE)
