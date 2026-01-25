
import pytest
import sys
from pathlib import Path

# Ensure root is in path if needed (though usually /app is WORKDIR)
sys.path.append("/app")

from src.cad_engine import CADEngine
from src.renderer import Renderer
from examples.demo_parts import PARTS

def test_visual_flange(tmp_path):
    """Test visual generation for Flange part."""
    # Setup
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "renders"
    workspace.mkdir()
    output_dir.mkdir()
    
    engine = CADEngine(workspace=workspace)
    renderer = Renderer(output_dir=output_dir)
    
    # Create Model
    code = PARTS["flange"]
    result = engine.execute_code(code, "flange_test")
    
    assert result["success"], f"Failed to create model: {result.get('error')}"
    
    # 1. Test Shading (Iso view)
    path_3d = renderer.render_3d(
        engine.get_model("flange_test").shape, 
        view="iso", 
        filename="verify_flange_3d.png"
    )
    assert path_3d.exists()
    assert path_3d.stat().st_size > 0, "3D render is empty"

    # 2. Test Title Block (2D view with metadata)
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
    assert path_2d.exists()
    assert path_2d.stat().st_size > 0, "2D render is empty"
