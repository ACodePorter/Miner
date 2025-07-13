#!/bin/bash

echo "🔄 Restarting StkGuru development server..."

# Kill any existing Vite processes
echo "📋 Stopping existing Vite processes..."
pkill -f "vite" || true

# Clear node_modules cache if needed
if [ "$1" = "--clear-cache" ]; then
    echo "🧹 Clearing node_modules cache..."
    rm -rf node_modules/.vite
    rm -rf node_modules/.cache
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start the development server
echo "🚀 Starting development server..."
npm run dev

echo "✅ Development server started!"
echo "🌐 Open http://localhost:5173 in your browser"
echo "🔧 If you still have issues, try:"
echo "   - Opening Chrome in incognito mode"
echo "   - Visiting http://localhost:5173/clear-cache.html"
echo "   - Disabling browser extensions" 