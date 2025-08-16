#!/usr/bin/env python3
"""
Simple test server to verify port binding works correctly on Render
"""
import os
import asyncio
from aiohttp import web

async def health_check(request):
    return web.Response(text="OK", status=200)

async def hello(request):
    return web.Response(text="Hello from test server!", status=200)

async def start_server():
    port = int(os.environ.get('PORT', 10000))
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', hello)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"Test server running on port {port}")
    print(f"Health check available at: http://0.0.0.0:{port}/health")
    print(f"Hello endpoint available at: http://0.0.0.0:{port}/")
    
    return runner

if __name__ == "__main__":
    asyncio.run(start_server())
