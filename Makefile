.PHONY: start stop status install

# Start all services (Redis + Backend + Frontend)
start:
	@echo "🚀 Starting FinSight CFO Assistant..."
	@# Start Redis if not running
	@docker start redis-finsight 2>/dev/null || docker run -d --name redis-finsight -p 6379:6379 redis:alpine
	@echo "✅ Redis running on localhost:6379"
	@# Start backend in background
	@cd $(CURDIR) && PYTHONPATH=. conda run --no-banner -n finsight uvicorn backend.api.main:app --reload --port 8000 &
	@sleep 2
	@echo "✅ Backend running on http://localhost:8000"
	@# Start frontend in background
	@cd $(CURDIR)/frontend && npm run dev &
	@sleep 2
	@echo "✅ Frontend running on http://localhost:5173"
	@echo ""
	@echo "🎉 FinSight is ready! Open http://localhost:5173"
	@echo "   Press Ctrl+C to stop all services"
	@wait

# Stop all services
stop:
	@echo "Stopping FinSight..."
	@-pkill -f "uvicorn backend.api.main:app" 2>/dev/null
	@-pkill -f "vite" 2>/dev/null
	@-docker stop redis-finsight 2>/dev/null
	@echo "✅ All services stopped"

# Check service status
status:
	@echo "=== FinSight Status ==="
	@docker ps --filter name=redis-finsight --format "Redis: {{.Status}}" 2>/dev/null || echo "Redis: not running"
	@curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool || echo "Backend: not running"
	@curl -s http://localhost:5173 >/dev/null 2>&1 && echo "Frontend: running" || echo "Frontend: not running"

# First-time setup
install:
	@echo "📦 Installing dependencies..."
	conda create -n finsight python=3.13 -y 2>/dev/null || true
	cd $(CURDIR) && conda run --no-banner -n finsight pip install -r backend/requirements.txt
	cd $(CURDIR)/frontend && npm install
	@echo "✅ Dependencies installed"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy backend/.env.example to backend/.env and add your API keys"
	@echo "  2. Create Pinecone index 'finsight-index' (dim=3072, cosine)"
	@echo "  3. Run: make start"
