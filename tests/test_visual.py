from src.cad_engine import CADEngine
from src.renderer import Renderer
from pathlib import Path
import os
import sys

# Mock sys.modules if needed, but we run inside docker so it's fine

def test_visual_flange():
    print("Testing visual generation for Flange...")
    engine = CADEngine(workspace=Path("/tmp/test_workspace"))
    
    # Import PARTS
    sys.path.append("/app") # Ensure root is in path
    from examples.demo_parts import PARTS
    
    code = PARTS["flange"]
    result = engine.execute_code(code, "flange_test")
    
    if not result["success"]:
        print(f"Failed to create model: {result['error']}")
        exit(1)
        
    print("Model created successfully.")
    
    # Use a directory we can check (renders is mounted in docker run typically)
    renderer = Renderer(output_dir=Path("/renders"))
    
    # 1. Test Shading (Iso view)
    print("Rendering 3D Iso...")
    path_3d = renderer.render_3d(
        engine.get_model("flange_test").shape, 
        view="iso", 
        filename="verify_flange_3d.png"
    )
    if path_3d.exists() and path_3d.stat().st_size > 0:
        print(f"✓ 3D Render generated: {path_3d} ({path_3d.stat().st_size} bytes)")
    else:
        print("✗ 3D Render failed")
        exit(1)

    # 2. Test Title Block (2D view with metadata)
    print("Rendering 2D with Title Block...")
    metadata = {
        "title": "TEST FLANGE",
        "part_number": "F-101",
        "company": "TEST CORP",
        "drawn_by": "SISYPHUS"
    }
    path_2d = renderer.render_2d(
        engine.get_model("flange_test").shape,
        view="top",
        filename="verify_flange_titleblock.png",
        metadata=metadata
    )
    if path_2d.exists() and path_2d.stat().st_size > 0:
        print(f"✓ 2D Render generated: {path_2d} ({path_2d.stat().st_size} bytes)")
    else:
        print("✗ 2D Render failed")
        exit(1)

    print("Visual verification passed!")

if __name__ == "__main__":
    test_visual_flange()
