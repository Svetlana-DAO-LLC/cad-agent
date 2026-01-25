"""
VTK-based CAD Renderer with proper orthographic/isometric projections.

Provides high-quality 3D rendering with correct proportions using VTK's
offscreen rendering capability with Xvfb virtual framebuffer.

Usage:
    from vtk_renderer import VTKRenderer
    renderer = VTKRenderer()
    renderer.render_stl('/path/to/model.stl', view='iso', output='/path/to/output.png')
"""

import os
import subprocess
import signal
import tempfile
import math
from pathlib import Path
from typing import Literal, Optional, Tuple
from dataclasses import dataclass

import numpy as np

ViewAngle = Literal["front", "back", "left", "right", "top", "bottom", "iso", "iso_back", "iso_front_left", "iso_back_left"]


@dataclass
class VTKRenderConfig:
    """Configuration for VTK rendering."""
    width: int = 1024
    height: int = 768
    background_color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    model_color: Tuple[float, float, float] = (0.4, 0.6, 0.8)
    edge_color: Tuple[float, float, float] = (0.1, 0.1, 0.1)
    show_edges: bool = False
    edge_width: float = 1.0
    specular: float = 0.3
    specular_power: float = 20.0
    ambient: float = 0.2
    diffuse: float = 0.8
    use_orthographic: bool = True  # True for CAD-style, False for perspective
    zoom_factor: float = 0.9  # Fill factor (0.0-1.0)
    antialiasing: int = 8  # Multi-sample anti-aliasing (0 to disable)


# Standard CAD view directions: (camera_offset_direction, view_up)
# Camera offset direction is normalized and multiplied by distance
VIEW_CONFIGS = {
    "front": {"offset": (0, -1, 0), "up": (0, 0, 1)},
    "back": {"offset": (0, 1, 0), "up": (0, 0, 1)},
    "left": {"offset": (-1, 0, 0), "up": (0, 0, 1)},
    "right": {"offset": (1, 0, 0), "up": (0, 0, 1)},
    "top": {"offset": (0, 0, 1), "up": (0, 1, 0)},
    "bottom": {"offset": (0, 0, -1), "up": (0, -1, 0)},
    "iso": {"offset": (1, -1, 0.8), "up": (0, 0, 1)},
    "iso_back": {"offset": (-1, 1, 0.8), "up": (0, 0, 1)},
    "iso_front_left": {"offset": (-1, -1, 0.8), "up": (0, 0, 1)},
    "iso_back_left": {"offset": (1, 1, 0.8), "up": (0, 0, 1)},
}


class XvfbManager:
    """Manages Xvfb virtual framebuffer for headless rendering."""
    
    def __init__(self, display: int = 99, screen_size: str = "1280x1024x24"):
        self.display = display
        self.screen_size = screen_size
        self.process = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()
    
    def start(self):
        """Start Xvfb if not already running."""
        # Check if display already exists
        lock_file = f"/tmp/.X{self.display}-lock"
        if os.path.exists(lock_file):
            # Display might already be running
            os.environ["DISPLAY"] = f":{self.display}"
            return
        
        try:
            self.process = subprocess.Popen(
                ["Xvfb", f":{self.display}", "-screen", "0", self.screen_size],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            # Wait a bit for Xvfb to start
            import time
            time.sleep(0.5)
            os.environ["DISPLAY"] = f":{self.display}"
        except FileNotFoundError:
            raise RuntimeError("Xvfb not installed. Run: apt-get install xvfb")
    
    def stop(self):
        """Stop Xvfb process."""
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            self.process = None


class VTKRenderer:
    """
    High-quality VTK-based renderer for CAD models.
    
    Supports:
    - Orthographic and perspective projections
    - Multiple standard CAD views
    - Proper aspect ratio preservation
    - Anti-aliasing
    - Headless rendering via Xvfb
    """
    
    def __init__(self, config: VTKRenderConfig = None, output_dir: Path = Path("/renders")):
        self.config = config or VTKRenderConfig()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._xvfb = None
    
    def _ensure_display(self):
        """Ensure a display is available for VTK."""
        if os.environ.get("DISPLAY"):
            return
        self._xvfb = XvfbManager()
        self._xvfb.start()
    
    def render_stl(self, stl_path: str, view: ViewAngle = "iso",
                   output: str = None, title: str = None) -> Path:
        """
        Render an STL file from the specified view angle.
        
        Args:
            stl_path: Path to the STL file
            view: View angle (front, back, left, right, top, bottom, iso, iso_back)
            output: Output PNG path (default: auto-generated in output_dir)
            title: Optional title to overlay on the image
            
        Returns:
            Path to the rendered PNG file
        """
        self._ensure_display()
        
        import vtk
        
        stl_path = Path(stl_path)
        if not stl_path.exists():
            raise FileNotFoundError(f"STL file not found: {stl_path}")
        
        if output is None:
            output = self.output_dir / f"{stl_path.stem}_{view}.png"
        else:
            output = Path(output)
        
        # Load STL
        reader = vtk.vtkSTLReader()
        reader.SetFileName(str(stl_path))
        reader.Update()
        
        polydata = reader.GetOutput()
        
        # Render
        self._render_polydata(polydata, view, output, title)
        
        return output
    
    def render_trimesh(self, mesh, view: ViewAngle = "iso",
                       output: str = None, title: str = None) -> Path:
        """
        Render a trimesh mesh from the specified view angle.
        
        Args:
            mesh: trimesh.Trimesh object
            view: View angle
            output: Output PNG path
            title: Optional title
            
        Returns:
            Path to the rendered PNG file
        """
        import trimesh
        
        # Export to temp STL
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            tmp_path = f.name
        
        mesh.export(tmp_path, file_type='stl')
        result = self.render_stl(tmp_path, view, output, title)
        
        os.unlink(tmp_path)
        return result
    
    def render_build123d(self, shape, view: ViewAngle = "iso",
                         output: str = None, title: str = None) -> Path:
        """
        Render a build123d shape from the specified view angle.
        
        Args:
            shape: build123d Shape object
            view: View angle
            output: Output PNG path
            title: Optional title
            
        Returns:
            Path to the rendered PNG file
        """
        from build123d import export_stl
        
        # Export to temp STL
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            tmp_path = f.name
        
        export_stl(shape, tmp_path)
        result = self.render_stl(tmp_path, view, output, title)
        
        os.unlink(tmp_path)
        return result
    
    def render_multiview(self, stl_path: str, views: list = None,
                         output: str = None, title: str = None) -> Path:
        """
        Render multiple views in a grid layout.
        
        Args:
            stl_path: Path to STL file
            views: List of view angles (default: front, right, top, iso)
            output: Output PNG path
            title: Optional title
            
        Returns:
            Path to the rendered PNG file
        """
        from PIL import Image
        
        if views is None:
            views = ["front", "right", "top", "iso"]
        
        stl_path = Path(stl_path)
        if output is None:
            output = self.output_dir / f"{stl_path.stem}_multiview.png"
        else:
            output = Path(output)
        
        # Render each view
        images = []
        for view in views:
            tmp_output = self.output_dir / f"_tmp_{view}.png"
            self.render_stl(stl_path, view=view, output=tmp_output)
            images.append((view, Image.open(tmp_output)))
        
        # Compose grid
        n = len(images)
        if n <= 2:
            cols, rows = n, 1
        elif n <= 4:
            cols, rows = 2, 2
        elif n <= 6:
            cols, rows = 3, 2
        else:
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
        
        cell_w = self.config.width
        cell_h = self.config.height
        
        composite = Image.new('RGB', (cols * cell_w, rows * cell_h), 
                              tuple(int(c * 255) for c in self.config.background_color))
        
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(composite)
        
        for idx, (view_name, img) in enumerate(images):
            row = idx // cols
            col = idx % cols
            x = col * cell_w
            y = row * cell_h
            
            composite.paste(img, (x, y))
            
            # Add view label
            draw.rectangle([x, y, x + cell_w - 1, y + cell_h - 1], outline=(180, 180, 180), width=1)
            draw.text((x + 10, y + 10), view_name.upper(), fill=(80, 80, 80))
        
        # Add title if provided
        if title:
            draw.rectangle([0, 0, cols * cell_w, 30], fill=(240, 240, 240))
            draw.text((10, 5), title, fill=(0, 0, 0))
        
        composite.save(output)
        
        # Cleanup temp files
        for view, _ in images:
            tmp = self.output_dir / f"_tmp_{view}.png"
            tmp.unlink(missing_ok=True)
        
        return output
    
    def render_comparison(self, stl_paths: list, view: ViewAngle = "iso",
                          output: str = None, labels: list = None) -> Path:
        """
        Render multiple STL files side by side for comparison.
        
        Args:
            stl_paths: List of STL file paths
            view: View angle for all
            output: Output PNG path
            labels: Optional labels for each model
            
        Returns:
            Path to the rendered PNG file
        """
        from PIL import Image, ImageDraw
        
        if output is None:
            output = self.output_dir / "comparison.png"
        else:
            output = Path(output)
        
        if labels is None:
            labels = [Path(p).stem for p in stl_paths]
        
        # Render each
        images = []
        for stl_path in stl_paths:
            tmp_output = self.output_dir / f"_tmp_cmp_{Path(stl_path).stem}.png"
            self.render_stl(stl_path, view=view, output=tmp_output)
            images.append(Image.open(tmp_output))
        
        # Side by side
        n = len(images)
        cell_w = self.config.width
        cell_h = self.config.height
        
        composite = Image.new('RGB', (n * cell_w, cell_h + 30),
                              tuple(int(c * 255) for c in self.config.background_color))
        draw = ImageDraw.Draw(composite)
        
        for idx, (img, label) in enumerate(zip(images, labels)):
            x = idx * cell_w
            composite.paste(img, (x, 30))
            draw.rectangle([x, 0, x + cell_w, 30], fill=(240, 240, 240), outline=(180, 180, 180))
            draw.text((x + 10, 5), label, fill=(0, 0, 0))
        
        composite.save(output)
        
        # Cleanup
        for stl_path in stl_paths:
            tmp = self.output_dir / f"_tmp_cmp_{Path(stl_path).stem}.png"
            tmp.unlink(missing_ok=True)
        
        return output
    
    def _render_polydata(self, polydata, view: ViewAngle, output: Path, title: str = None):
        """Internal method to render VTK polydata."""
        import vtk
        
        # Compute normals for better shading
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputData(polydata)
        normals.ComputePointNormalsOn()
        normals.ComputeCellNormalsOn()
        normals.SplittingOn()
        normals.SetFeatureAngle(30.0)
        normals.Update()
        
        # Mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        
        # Actor
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        
        prop = actor.GetProperty()
        prop.SetColor(*self.config.model_color)
        prop.SetSpecular(self.config.specular)
        prop.SetSpecularPower(self.config.specular_power)
        prop.SetAmbient(self.config.ambient)
        prop.SetDiffuse(self.config.diffuse)
        
        if self.config.show_edges:
            prop.EdgeVisibilityOn()
            prop.SetEdgeColor(*self.config.edge_color)
            prop.SetLineWidth(self.config.edge_width)
        
        # Renderer
        renderer = vtk.vtkRenderer()
        renderer.AddActor(actor)
        renderer.SetBackground(*self.config.background_color)
        
        # Add subtle ambient lighting
        renderer.SetAmbient(0.3, 0.3, 0.3)
        
        # Add lights
        light1 = vtk.vtkLight()
        light1.SetPosition(1, 1, 1)
        light1.SetFocalPoint(0, 0, 0)
        light1.SetIntensity(0.8)
        renderer.AddLight(light1)
        
        light2 = vtk.vtkLight()
        light2.SetPosition(-1, -1, 0.5)
        light2.SetFocalPoint(0, 0, 0)
        light2.SetIntensity(0.4)
        renderer.AddLight(light2)
        
        # Camera setup
        bounds = polydata.GetBounds()
        center = [
            (bounds[0] + bounds[1]) / 2,
            (bounds[2] + bounds[3]) / 2,
            (bounds[4] + bounds[5]) / 2
        ]
        size = max(
            bounds[1] - bounds[0],
            bounds[3] - bounds[2],
            bounds[5] - bounds[4]
        )
        
        view_config = VIEW_CONFIGS.get(view, VIEW_CONFIGS["iso"])
        offset = np.array(view_config["offset"], dtype=float)
        offset = offset / np.linalg.norm(offset)  # Normalize
        up = view_config["up"]
        
        camera_distance = size * 2.0
        camera_pos = [
            center[0] + offset[0] * camera_distance,
            center[1] + offset[1] * camera_distance,
            center[2] + offset[2] * camera_distance
        ]
        
        camera = renderer.GetActiveCamera()
        camera.SetPosition(*camera_pos)
        camera.SetFocalPoint(*center)
        camera.SetViewUp(*up)
        
        if self.config.use_orthographic:
            camera.SetParallelProjection(True)
            # Calculate parallel scale to fit model with zoom factor
            # Account for aspect ratio
            aspect = self.config.width / self.config.height
            scale_h = size / 2 / self.config.zoom_factor
            scale_v = scale_h / aspect if aspect > 1 else scale_h
            camera.SetParallelScale(max(scale_h, scale_v))
        else:
            camera.SetParallelProjection(False)
            camera.SetViewAngle(30)  # FOV in degrees
        
        # Render window
        rw = vtk.vtkRenderWindow()
        rw.SetOffScreenRendering(1)
        rw.SetSize(self.config.width, self.config.height)
        rw.AddRenderer(renderer)
        
        if self.config.antialiasing > 0:
            rw.SetMultiSamples(self.config.antialiasing)
        
        rw.Render()
        
        # Capture image
        w2if = vtk.vtkWindowToImageFilter()
        w2if.SetInput(rw)
        w2if.SetInputBufferTypeToRGBA()
        w2if.Update()
        
        # Write PNG
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(output))
        writer.SetInputConnection(w2if.GetOutputPort())
        writer.Write()
        
        # Add title if provided (using PIL post-processing)
        if title:
            self._add_title(output, title, view)
    
    def _add_title(self, image_path: Path, title: str, view: str):
        """Add title and view label to rendered image."""
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        # Try to load a nice font, fall back to default
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except:
            font = ImageFont.load_default()
            font_small = font
        
        # Add view label in corner
        draw.text((10, img.height - 25), view.upper(), fill=(100, 100, 100), font=font_small)
        
        # Add title at top
        if title:
            # Semi-transparent background for title
            draw.rectangle([0, 0, img.width, 28], fill=(245, 245, 245))
            draw.text((10, 5), title, fill=(50, 50, 50), font=font)
        
        img.save(image_path)


def render_stl_quick(stl_path: str, view: str = "iso", output: str = None) -> Path:
    """
    Quick helper function to render an STL with default settings.
    
    Usage:
        from vtk_renderer import render_stl_quick
        render_stl_quick('/workspace/model.stl', 'iso', '/workspace/render.png')
    """
    renderer = VTKRenderer()
    return renderer.render_stl(stl_path, view=view, output=output)


if __name__ == "__main__":
    # Test rendering
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python vtk_renderer.py <stl_file> [view] [output]")
        print("Views: front, back, left, right, top, bottom, iso, iso_back")
        sys.exit(1)
    
    stl_file = sys.argv[1]
    view = sys.argv[2] if len(sys.argv) > 2 else "iso"
    output = sys.argv[3] if len(sys.argv) > 3 else None
    
    renderer = VTKRenderer()
    result = renderer.render_stl(stl_file, view=view, output=output)
    print(f"Rendered to: {result}")
