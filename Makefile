.PHONY: start stop status doctor stats cleanup-orphans install

# Pin to the finsight env's binaries directly. `conda run -n finsight` is
# unreliable when a system-Python uvicorn exists earlier on PATH — it will
# launch the wrong uvicorn against the wrong Python and fail with
# `ModuleNotFoundError: No module named 'fastapi'`.
FINSIGHT_BIN := $(HOME)/miniconda3/envs/finsight/bin

# ── start: bring up Redis + Backend + Frontend; health-gate before declaring ready ─
start:
	@mkdir -p logs
	@echo "🚀 Starting FinSight CFO Assistant..."
	@# Start Redis if not running
	@docker start redis-finsight 2>/dev/null || docker run -d --name redis-finsight -p 6379:6379 redis:alpine
	@echo "✅ Redis running on localhost:6379"
	@# Start backend in background with logs captured to logs/backend.log
	@cd $(CURDIR) && PYTHONPATH=. $(FINSIGHT_BIN)/uvicorn backend.api.main:app --reload --port 8000 > logs/backend.log 2>&1 &
	@printf "⏳ Waiting for backend /health..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
		if curl -sf http://localhost:8000/health >/dev/null 2>&1; then break; fi; \
		printf "."; sleep 1; \
	done; \
	echo ""
	@if curl -sf http://localhost:8000/health >/dev/null 2>&1; then \
		echo "✅ Backend healthy at http://localhost:8000"; \
	else \
		echo "❌ Backend failed to start within 15s — last 20 lines of logs/backend.log:"; \
		tail -20 logs/backend.log; \
		echo ""; \
		echo "Run 'make doctor' to diagnose."; \
		exit 1; \
	fi
	@# Start frontend in background with logs captured to logs/frontend.log
	@cd $(CURDIR)/frontend && npm run dev > ../logs/frontend.log 2>&1 &
	@sleep 2
	@echo "✅ Frontend running on http://localhost:5173"
	@echo ""
	@echo "🎉 FinSight is ready! Open http://localhost:5173"
	@echo "   Follow logs: tail -f logs/backend.log   tail -f logs/frontend.log"
	@echo "   Press Ctrl+C to stop all services"
	@wait

# ── stop: terminate all three services ───────────────────────────────────────
stop:
	@echo "Stopping FinSight..."
	@-pkill -f "uvicorn backend.api.main:app" 2>/dev/null
	@-pkill -f "vite" 2>/dev/null
	@-docker stop redis-finsight 2>/dev/null
	@echo "✅ All services stopped"

# ── status: quick one-shot status snapshot ───────────────────────────────────
status:
	@echo "=== FinSight Status ==="
	@docker ps --filter name=redis-finsight --format "Redis: {{.Status}}" 2>/dev/null || echo "Redis: not running"
	@curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool || echo "Backend: not running"
	@curl -s http://localhost:5173 >/dev/null 2>&1 && echo "Frontend: running" || echo "Frontend: not running"

# ── doctor: diagnose why the app isn't starting (exits 1 on any failure) ──────
doctor:
	@echo "=== FinSight Doctor ==="
	@fails=0; \
	if docker ps --filter name=redis-finsight --format '{{.Names}}' | grep -q redis-finsight; then \
		echo "  ✅ Redis container     : Up"; \
	else \
		echo "  ❌ Redis container     : NOT RUNNING — try: docker start redis-finsight"; \
		fails=$$((fails+1)); \
	fi; \
	if [ -x $(FINSIGHT_BIN)/uvicorn ]; then \
		echo "  ✅ finsight uvicorn    : $(FINSIGHT_BIN)/uvicorn"; \
		shadow=$$(command -v uvicorn 2>/dev/null); \
		if [ -n "$$shadow" ] && [ "$$shadow" != "$(FINSIGHT_BIN)/uvicorn" ]; then \
			echo "     ⚠️  PATH shadow       : $$shadow (Makefile pins absolute path, so 'make start' is safe)"; \
		fi; \
	else \
		echo "  ❌ finsight uvicorn    : MISSING at $(FINSIGHT_BIN)/uvicorn — run: make install"; \
		fails=$$((fails+1)); \
	fi; \
	if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then \
		echo "  ✅ Port 8000           : listening"; \
	else \
		echo "  ❌ Port 8000           : nothing listening — run: make start"; \
		fails=$$((fails+1)); \
	fi; \
	if curl -sf http://localhost:8000/health >/dev/null 2>&1; then \
		echo "  ✅ Backend /health     : 200 OK"; \
	else \
		echo "  ❌ Backend /health     : unreachable (backend crashed or not started)"; \
		fails=$$((fails+1)); \
	fi; \
	if lsof -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then \
		echo "  ✅ Frontend (port 5173): listening"; \
	else \
		echo "  ⚠️  Frontend (port 5173): not running (optional for backend-only work)"; \
	fi; \
	if [ -f backend/.env ]; then \
		echo "  ✅ backend/.env        : exists"; \
		for key in ANTHROPIC_API_KEY GEMINI_API_KEY PINECONE_API_KEY; do \
			if grep -qE "^$$key=.+" backend/.env; then \
				echo "     ✅ $$key: set"; \
			else \
				echo "     ❌ $$key: missing or empty"; \
				fails=$$((fails+1)); \
			fi; \
		done; \
	else \
		echo "  ❌ backend/.env        : missing — copy backend/.env.example to backend/.env"; \
		fails=$$((fails+1)); \
	fi; \
	if [ -d logs ]; then \
		echo "  ✅ logs/               : exists"; \
	else \
		echo "  ℹ️  logs/               : will be created by 'make start'"; \
	fi; \
	echo ""; \
	if [ $$fails -eq 0 ]; then \
		echo "✅ All required checks passed."; \
	else \
		echo "❌ $$fails check(s) failed. See hints above."; \
		exit 1; \
	fi

# ── stats: cross-referenced Pinecone + Redis snapshot (orphan detection) ─────
stats:
	@cd $(CURDIR) && PYTHONPATH=. $(FINSIGHT_BIN)/python -m backend.scripts.stats

# ── cleanup-orphans: remove Pinecone vectors with no Redis registry entry ────
cleanup-orphans:
	@cd $(CURDIR) && PYTHONPATH=. $(FINSIGHT_BIN)/python backend/scripts/cleanup_orphans.py $(if $(APPLY),--apply,)

# ── install: first-time setup ────────────────────────────────────────────────
install:
	@echo "📦 Installing dependencies..."
	conda create -n finsight python=3.13 -y 2>/dev/null || true
	cd $(CURDIR) && conda run -n finsight pip install -r backend/requirements.txt
	cd $(CURDIR)/frontend && npm install
	@echo "✅ Dependencies installed"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy backend/.env.example to backend/.env and add your API keys"
	@echo "  2. Create Pinecone index 'finsight-index' (dim=3072, cosine)"
	@echo "  3. Run: make doctor   (verify infra)"
	@echo "  4. Run: make start    (launch everything)"
