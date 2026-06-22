.PHONY: help service-start service-stop service-status service-restart clean

help:
	@echo "Available commands:"
	@echo "  make service-start            Start all services (Docker Compose, background)"
	@echo "  make service-start s=<name>   Start a specific service (e.g. s=neo4j)"
	@echo "  make service-stop             Stop all services"
	@echo "  make service-stop s=<name>    Stop a specific service (e.g. s=neo4j)"
	@echo "  make service-status           Show status of all services"
	@echo "  make service-restart          Restart all services"
	@echo "  make service-restart s=<name> Restart a specific service (e.g. s=neo4j)"
	@echo "  make clean                    Stop all services and delete all data and volumes"

service-start:
	@if [ -z "$(s)" ]; then \
		docker compose up -d; \
	else \
		docker compose up -d $(s); \
	fi
	@echo "Waiting for services to become healthy..."
	@while docker compose ps | grep -q "health: starting"; do \
		printf "."; \
		sleep 2; \
	done
	@echo ""
	@echo "All services are healthy."
	@echo ""
	@$(MAKE) --no-print-directory service-status

service-stop:
	@if [ -z "$(s)" ]; then \
		docker compose down; \
	else \
		docker compose stop $(s); \
	fi

service-status:
	@docker compose ps --format "table {{.Name}}\t{{.Service}}\t{{.Status}}\t{{.Health}}"

service-restart:
	@if [ -z "$(s)" ]; then \
		docker compose restart; \
	else \
		docker compose restart $(s); \
	fi

clean:
	docker compose down -v
	rm -rf data/
