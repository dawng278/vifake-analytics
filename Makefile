.DEFAULT_GOAL := help

.PHONY: demo test stop logs help

# ─────────────────────────────────────────────────────────────
#  ViFake Analytics — Demo Makefile
#  Requires: Docker + Docker Compose v2
# ─────────────────────────────────────────────────────────────

demo:            ## 🚀  Build & start everything (API + Web UI)
	@echo "────────────────────────────────────────────"
	@echo "  ViFake Analytics — starting demo stack..."
	@echo "────────────────────────────────────────────"
	docker compose up --build -d
	@echo ""
	@echo "  ✅  Web UI  → http://localhost:8080"
	@echo "  ✅  API     → http://localhost:8000"
	@echo "  ✅  API docs → http://localhost:8000/docs"
	@echo ""
	@echo "  Run 'make logs' to follow logs"
	@echo "  Run 'make stop' to shut down"
	@echo "────────────────────────────────────────────"

stop:            ## 🛑  Stop and remove containers
	docker compose down
	@echo "  Stopped."

logs:            ## 📋  Follow API logs
	docker compose logs -f api

test:            ## 🧪  Run test suite inside running API container
	docker compose exec api python -m pytest test_enhanced_ai.py -v --tb=short

help:            ## ℹ️   Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
