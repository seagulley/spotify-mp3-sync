#!/bin/bash

echo "🚀 Starting Spotify MP3 Sync Backend..."

# Kill existing processes
echo "🔄 Cleaning up existing processes..."
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "lt --port 8000" 2>/dev/null

# Start localtunnel with custom subdomain
echo "🌐 Starting localtunnel with custom subdomain..."
lt --port 8000 --subdomain spotisync &
LT_PID=$!

# Wait for localtunnel to start
echo "⏳ Waiting for localtunnel to start..."
sleep 5

# Get the URL
echo "📡 Getting localtunnel URL..."
LT_URL="https://spotisync.loca.lt"

echo "✅ LocalTunnel URL: $LT_URL"

# Start backend
echo "🔧 Starting backend..."
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo ""
echo "🎉 Setup complete!"
echo "📱 Backend URL: $LT_URL"
echo "🔗 Spotify Redirect URI: $LT_URL/callback"
echo ""
echo "⚠️  Don't forget to add the redirect URI to your Spotify app!"
echo "   Go to: https://developer.spotify.com/dashboard"
echo "   Add: $LT_URL/callback"
echo ""
echo "Press Ctrl+C to stop all processes"

# Wait for interrupt
trap "echo '🛑 Shutting down...'; kill $LT_PID $BACKEND_PID 2>/dev/null; exit" INT
wait 