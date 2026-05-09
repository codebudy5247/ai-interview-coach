#!/bin/bash
set -a
source .env
source backend/.env
set +a

echo "Starting Interview Coach dev servers..."

echo "Starting backend..."
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Starting frontend..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo "Interview Coach is running:"
echo "  Backend: http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

wait