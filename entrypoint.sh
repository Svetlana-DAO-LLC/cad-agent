#!/bin/bash
set -e

# Start Xvfb for headless VTK rendering
start_xvfb() {
    if ! pgrep -x Xvfb > /dev/null; then
        echo "Starting Xvfb virtual framebuffer..." >&2
        Xvfb :99 -screen 0 1280x1024x24 &>/dev/null &
        sleep 0.5
    fi
    export DISPLAY=:99
}

case "$1" in
    serve|http)
        start_xvfb
        echo "Starting CAD Agent HTTP server on port 8123..."
        exec python -m src.mcp_server http --host 0.0.0.0 --port 8123
        ;;
    mcp)
        start_xvfb
        echo "Starting CAD Agent MCP server on stdio..." >&2
        exec python -m src.mcp_server mcp
        ;;
    test)
        start_xvfb
        echo "Running self-test..."
        if python -c "import pytest" 2>/dev/null; then
            echo "Running pytest..."
            exec python -m pytest tests/ -v
        else
            echo "Pytest not found, running legacy self-test..."
            exec python -c "
from src.cad_engine import CADEngine
from src.renderer import Renderer

engine = CADEngine()
result = engine.execute_code('''
from build123d import *
result = Box(20, 30, 10)
''', 'test_box')

print('Create model:', 'OK' if result['success'] else 'FAIL')
print('Geometry:', result.get('geometry'))

if result['success']:
    model = engine.get_model('test_box')
    renderer = Renderer()
    
    # Test 3D render
    path_3d = renderer.render_3d(model.shape, 'iso', 'test_3d.png')
    print(f'3D render: {path_3d}')
    
    # Test 2D render
    path_2d = renderer.render_2d(model.shape, 'front', True, True, 'test_2d.png')
    print(f'2D render: {path_2d}')
    
    # Test measurements
    measurements = engine.measure('test_box')
    print(f'Measurements: {measurements}')
    
    print('\\nAll tests PASSED ✓')
"
        fi
        ;;
    shell)
        exec /bin/bash
        ;;
    *)
        echo "Usage: $0 {serve|mcp|test|shell}"
        echo "  serve/http - Start HTTP REST API server (port 8123)"
        echo "  mcp        - Start MCP stdio server"
        echo "  test       - Run self-test"
        echo "  shell      - Interactive shell"
        exit 1
        ;;
esac
