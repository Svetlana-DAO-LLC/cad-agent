#!/bin/bash
set -e

case "$1" in
    serve|http)
        echo "Starting CAD Agent HTTP server on port 8123..."
        exec python -m src.mcp_server http --host 0.0.0.0 --port 8123
        ;;
    mcp)
        echo "Starting CAD Agent MCP server on stdio..." >&2
        exec python -m src.mcp_server mcp
        ;;
    test)
        echo "Running self-test..."
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
