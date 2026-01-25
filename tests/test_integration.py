"""
Integration tests for CAD Agent.
Run inside Docker: docker run --rm cad-agent:latest python -m pytest tests/ -v
"""

import json
import urllib.request
from pathlib import Path

API = "http://localhost:8123"


def api_call(endpoint, data=None, method="GET"):
    """Helper to make API calls."""
    if data:
        req = urllib.request.Request(
            f"{API}{endpoint}",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method=method or "POST"
        )
    else:
        req = urllib.request.Request(f"{API}{endpoint}")
    
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode())


def test_direct_engine():
    """Test CAD engine directly (no HTTP)."""
    from src.cad_engine import CADEngine
    
    engine = CADEngine(workspace=Path("/tmp/test_workspace"))
    
    # Create a simple box
    result = engine.execute_code("""
from build123d import *
result = Box(30, 20, 10)
""", "test_box")
    
    assert result["success"], f"Failed: {result.get('error')}"
    assert result["geometry"]["bounding_box"]["size"] == [30.0, 20.0, 10.0]
    
    # Measure
    measurements = engine.measure("test_box")
    assert measurements["volume_mm3"] == 6000.0
    assert measurements["face_count"] == 6
    assert measurements["edge_count"] == 12
    assert measurements["vertex_count"] == 8


def test_direct_renderer():
    """Test renderer directly."""
    from src.cad_engine import CADEngine
    from src.renderer import Renderer, RenderConfig
    
    engine = CADEngine(workspace=Path("/tmp/test_workspace"))
    engine.execute_code("from build123d import *\nresult = Cylinder(10, 20)", "test_cyl")
    
    model = engine.get_model("test_cyl")
    assert model is not None
    
    renderer = Renderer(output_dir=Path("/tmp/test_renders"))
    
    # 3D render
    path = renderer.render_3d(model.shape, "iso", "test_iso.png")
    assert path.exists()
    assert path.stat().st_size > 1000  # Should be a real image
    
    # 2D render
    path = renderer.render_2d(model.shape, "front", True, True, "test_front.png")
    assert path.exists()
    
    # Multiview
    path = renderer.render_multiview(model.shape, filename="test_multi.png")
    assert path.exists()


def test_direct_dimensioner():
    """Test dimensioner directly."""
    from src.cad_engine import CADEngine
    from src.dimensioner import Dimensioner
    
    engine = CADEngine(workspace=Path("/tmp/test_workspace"))
    engine.execute_code("""
from build123d import *
with BuildPart() as part:
    Cylinder(15, 30, align=(Align.CENTER, Align.CENTER, Align.MIN))
    Cylinder(5, 30, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
result = part.part
""", "test_dims")
    
    model = engine.get_model("test_dims")
    dimensioner = Dimensioner()
    
    dims = dimensioner.analyze(model.shape)
    assert len(dims) > 0
    
    # Should find the outer and inner diameters
    summary = dimensioner.get_dimension_summary(model.shape)
    diameters = [f for f in summary["features"] if f["type"] == "diameter"]
    assert len(diameters) >= 1  # At least the outer diameter


def test_direct_export():
    """Test STL/STEP export."""
    from src.cad_engine import CADEngine
    
    engine = CADEngine(workspace=Path("/tmp/test_workspace"))
    engine.execute_code("from build123d import *\nresult = Box(10, 10, 10)", "test_export")
    
    # STL
    stl_path = engine.export_model("test_export", "stl")
    assert stl_path.exists()
    assert stl_path.stat().st_size > 100
    
    # STEP
    step_path = engine.export_model("test_export", "step")
    assert step_path.exists()
    assert step_path.stat().st_size > 100

    # 3MF
    threemf_path = engine.export_model("test_export", "3mf")
    assert threemf_path.exists()
    assert threemf_path.stat().st_size > 100


def test_printability():
    """Test printability analysis."""
    from src.mcp_server import MCPServer
    
    server = MCPServer()
    server._create_model("from build123d import *\nresult = Box(20, 20, 20)", "test_print")
    
    analysis = server._analyze_printability("test_print")
    assert analysis["is_watertight"]
    assert analysis["is_volume"]
    assert analysis["printable"]
    assert len(analysis["issues"]) == 0


def test_error_handling():
    """Test that bad code doesn't crash the system."""
    from src.cad_engine import CADEngine
    
    engine = CADEngine(workspace=Path("/tmp/test_workspace"))
    
    # Syntax error
    result = engine.execute_code("this is not python!!!", "bad_code")
    assert not result["success"]
    assert "SyntaxError" in result["error"]
    
    # Runtime error
    result = engine.execute_code("from build123d import *\nx = 1/0", "div_zero")
    assert not result["success"]
    assert "ZeroDivisionError" in result["error"]
    
    # No shape produced
    result = engine.execute_code("x = 42", "no_shape")
    assert result["success"]  # Doesn't crash
    assert result["geometry"] is None


if __name__ == "__main__":
    print("Running integration tests...")
    
    tests = [
        test_direct_engine,
        test_direct_renderer,
        test_direct_dimensioner,
        test_direct_export,
        test_printability,
        test_error_handling,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
    
    print(f"\n{passed}/{passed + failed} tests passed")
    if failed:
        exit(1)
