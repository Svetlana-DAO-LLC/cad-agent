"""
CAD Renderer - 3D and 2D rendering for build123d models.

Provides:
- 3D perspective/isometric views via trimesh + pyrender (headless OSMesa)
- 2D orthographic technical drawings with dimensions via build123d's Drawing class
- Multi-view rendering (front, side, top, iso)
"""

import io
import math
import tempfile
from pathlib import Path
from typing import Any, Optional, Literal
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ViewAngle = Literal["front", "back", "left", "right", "top", "bottom", "iso", "iso_back"]

# Standard view directions (look_from vectors for build123d Drawing)
VIEW_DIRECTIONS: dict[ViewAngle, tuple] = {
    "front": (0, -1, 0),
    "back": (0, 1, 0),
    "left": (-1, 0, 0),
    "right": (1, 0, 0),
    "top": (0, 0, 1),
    "bottom": (0, 0, -1),
    "iso": (1, -1, 0.8),
    "iso_back": (-1, 1, 0.8),
}


@dataclass
class RenderConfig:
    """Configuration for rendering."""
    width: int = 1024
    height: int = 768
    background_color: tuple = (255, 255, 255, 255)
    edge_color: tuple = (0, 0, 0)
    hidden_color: tuple = (180, 180, 180)
    face_color: tuple = (100, 150, 200)
    face_opacity: float = 0.7
    line_width: float = 2.0
    hidden_line_width: float = 0.5
    show_axes: bool = True
    show_grid: bool = False
    show_dimensions: bool = True
    margin: int = 50
    font_size: int = 14


class Renderer:
    """
    Multi-mode renderer for build123d shapes.
    
    Supports:
    - 3D rendered views (trimesh + pyrender, headless)
    - 2D technical drawings (build123d HLR projection + SVG)
    - Multi-view layouts (engineering drawing style)
    """
    
    def __init__(self, config: RenderConfig = None, output_dir: Path = Path("/renders")):
        self.config = config or RenderConfig()
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def render_3d(self, shape: Any, view: ViewAngle = "iso",
                  filename: str = "render_3d.png") -> Path:
        """
        Render a 3D view of the shape using trimesh + pyrender.
        Falls back to wireframe if pyrender/OSMesa unavailable.
        """
        output_path = self.output_dir / filename
        
        try:
            return self._render_3d_pyrender(shape, view, output_path)
        except Exception as e:
            print(f"pyrender failed ({e}), falling back to trimesh")
            try:
                return self._render_3d_trimesh(shape, view, output_path)
            except Exception as e2:
                print(f"trimesh failed ({e2}), falling back to matplotlib")
                return self._render_3d_matplotlib(shape, view, output_path)
    
    def render_2d(self, shape: Any, view: ViewAngle = "front",
                  with_dimensions: bool = True,
                  with_hidden: bool = True,
                  filename: str = "render_2d.png",
                  metadata: dict = None) -> Path:
        """
        Render a 2D technical drawing view using build123d's HLR projection.
        """
        output_path = self.output_dir / filename
        
        from build123d.exporters import Drawing
        
        look_from = VIEW_DIRECTIONS.get(view, VIEW_DIRECTIONS["front"])
        
        # Choose appropriate up vector (can't be parallel to look_from)
        look_up = (0, 0, 1)
        if view in ("top", "bottom"):
            look_up = (0, -1, 0)  # Use Y as up for top/bottom views
        
        drawing = Drawing(shape, look_from=look_from, look_up=look_up, with_hidden=with_hidden)
        
        # Render to SVG then convert to PNG
        svg_content = self._drawing_to_svg(drawing, shape, view, with_dimensions, metadata)
        self._svg_to_png(svg_content, output_path)
        
        return output_path
    
    def render_multiview(self, shape: Any, 
                         views: list[ViewAngle] = None,
                         with_dimensions: bool = True,
                         filename: str = "multiview.png") -> Path:
        """
        Render a standard engineering multi-view drawing.
        Default: Front, Right, Top + Isometric
        """
        if views is None:
            views = ["front", "right", "top", "iso"]
        
        output_path = self.output_dir / filename
        
        # Render each view
        view_images = []
        for view in views:
            try:
                img_path = self.render_2d(
                    shape, view=view, 
                    with_dimensions=with_dimensions,
                    filename=f"_temp_{view}.png"
                )
                view_images.append((view, Image.open(img_path)))
            except Exception as e:
                print(f"Failed to render {view}: {e}")
                # Create placeholder
                img = Image.new('RGBA', (self.config.width // 2, self.config.height // 2), 
                               self.config.background_color)
                draw = ImageDraw.Draw(img)
                draw.text((10, 10), f"{view}\n(failed)", fill=(255, 0, 0))
                view_images.append((view, img))
        
        # Compose into multi-view layout
        composed = self._compose_multiview(view_images)
        composed.save(output_path)
        
        # Clean temp files
        for view in views:
            temp = self.output_dir / f"_temp_{view}.png"
            temp.unlink(missing_ok=True)
        
        return output_path
    
    def render_all(self, shape: Any, name: str = "model") -> dict[str, Path]:
        """Render all standard views. Returns dict of view_name -> path."""
        results = {}
        
        metadata = {"title": name, "part_number": name}
        
        # 3D isometric
        results["3d_iso"] = self.render_3d(shape, "iso", f"{name}_3d_iso.png")
        results["3d_iso_back"] = self.render_3d(shape, "iso_back", f"{name}_3d_iso_back.png")
        
        # 2D technical drawings
        for view in ["front", "right", "top"]:
            results[f"2d_{view}"] = self.render_2d(
                shape, view, with_dimensions=True, filename=f"{name}_2d_{view}.png",
                metadata=metadata
            )
        
        # Multi-view composite
        results["multiview"] = self.render_multiview(shape, filename=f"{name}_multiview.png")
        
        return results
    
    # --- Private rendering methods ---
    
    def _render_3d_pyrender(self, shape: Any, view: ViewAngle, output_path: Path) -> Path:
        """Render using pyrender with OSMesa backend."""
        import trimesh
        import pyrender
        
        # Export shape to STL, load with trimesh
        mesh = self._shape_to_trimesh(shape)
        
        # Create pyrender scene
        scene = pyrender.Scene(bg_color=np.array(self.config.background_color[:3]) / 255.0)
        
        # Add mesh
        material = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=np.array([*self.config.face_color, 255]) / 255.0,
            metallicFactor=0.2,
            roughnessFactor=0.6
        )
        mesh_node = pyrender.Mesh.from_trimesh(mesh, material=material)
        scene.add(mesh_node)
        
        # Add lights
        light = pyrender.DirectionalLight(color=np.ones(3), intensity=3.0)
        look_from = np.array(VIEW_DIRECTIONS[view], dtype=float)
        look_from = look_from / np.linalg.norm(look_from)
        
        # Camera setup
        camera = pyrender.PerspectiveCamera(yfov=np.pi / 4.0)
        
        # Calculate camera position based on model bounds
        bounds = mesh.bounds
        center = (bounds[0] + bounds[1]) / 2
        size = np.linalg.norm(bounds[1] - bounds[0])
        cam_distance = size * 2.0
        
        cam_pos = center + look_from * cam_distance
        cam_pose = self._look_at_matrix(cam_pos, center, np.array([0, 0, 1]))
        
        scene.add(camera, pose=cam_pose)
        scene.add(light, pose=cam_pose)
        
        # Add ambient light
        ambient = pyrender.DirectionalLight(color=np.ones(3), intensity=1.0)
        scene.add(ambient, pose=np.eye(4))
        
        # Render
        renderer = pyrender.OffscreenRenderer(self.config.width, self.config.height)
        color, depth = renderer.render(scene)
        renderer.delete()
        
        # Save
        img = Image.fromarray(color)
        
        # Add view label
        self._add_label(img, view.upper())
        
        img.save(output_path)
        return output_path
    
    def _render_3d_trimesh(self, shape: Any, view: ViewAngle, output_path: Path) -> Path:
        """Fallback render using trimesh's built-in renderer."""
        import trimesh
        
        mesh = self._shape_to_trimesh(shape)
        
        # Use trimesh scene rendering
        scene = trimesh.Scene(mesh)
        
        look_from = np.array(VIEW_DIRECTIONS[view], dtype=float)
        look_from = look_from / np.linalg.norm(look_from)
        
        bounds = mesh.bounds
        center = (bounds[0] + bounds[1]) / 2
        size = np.linalg.norm(bounds[1] - bounds[0])
        cam_distance = size * 2.5
        
        cam_pos = center + look_from * cam_distance
        
        # Try to render
        try:
            png_data = scene.save_image(resolution=(self.config.width, self.config.height))
            img = Image.open(io.BytesIO(png_data))
            img.save(output_path)
        except Exception:
            # If scene rendering fails, do wireframe via matplotlib
            return self._render_3d_matplotlib(shape, view, output_path)
        
        return output_path
    
    def _render_3d_matplotlib(self, shape: Any, view: ViewAngle, output_path: Path) -> Path:
        """Last-resort render using matplotlib 3D wireframe with custom shading."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        
        mesh = self._shape_to_trimesh(shape)
        
        # Calculate view parameters first to sort faces
        look_from = np.array(VIEW_DIRECTIONS[view], dtype=float)
        look_from = look_from / np.linalg.norm(look_from)
        
        # Camera position (approximate for sorting)
        bounds = mesh.bounds
        center = (bounds[0] + bounds[1]) / 2
        size = np.linalg.norm(bounds[1] - bounds[0])
        cam_pos = center + look_from * size * 2.0
        
        fig = plt.figure(figsize=(self.config.width / 100, self.config.height / 100), dpi=100)
        ax = fig.add_subplot(111, projection='3d')
        
        # Plot faces
        vertices = mesh.vertices
        faces = mesh.faces
        
        # Subsample if too many faces
        max_faces = 5000
        if len(faces) > max_faces:
            # Deterministic subsampling
            np.random.seed(42)
            indices = np.random.choice(len(faces), max_faces, replace=False)
            faces_subset = faces[indices]
        else:
            faces_subset = faces
            
        # Get actual triangles
        triangles = vertices[faces_subset]
        
        # Calculate face normals and centers for shading and sorting
        # Vectors for two edges of each triangle
        v0 = triangles[:, 0, :]
        v1 = triangles[:, 1, :]
        v2 = triangles[:, 2, :]
        
        # Face centers
        centers = (v0 + v1 + v2) / 3.0
        
        # Normals (cross product of edges)
        normals = np.cross(v1 - v0, v2 - v0)
        # Normalize
        norms = np.linalg.norm(normals, axis=1)
        # Avoid division by zero
        norms[norms == 0] = 1.0
        normals = normals / norms[:, np.newaxis]
        
        # Sorting: Calculate distance to camera for Painter's algorithm
        # Project centers onto look vector (depth)
        # We want to draw furthest faces first
        dists = np.dot(centers - cam_pos, -look_from)
        sort_indices = np.argsort(dists)
        
        triangles = triangles[sort_indices]
        normals = normals[sort_indices]
        
        # Lighting calculation
        # Light coming from top-right-front
        light_dir = np.array([1.0, 1.0, 1.0])
        light_dir = light_dir / np.linalg.norm(light_dir)
        
        # Lambertian shading: max(0, dot(normal, light))
        # We add some ambient light so back faces aren't pitch black
        intensity = np.dot(normals, light_dir)
        intensity = 0.5 + 0.5 * intensity  # Map -1..1 to 0..1 roughly, but keep contrast
        intensity = np.clip(intensity, 0.2, 1.0)  # Min ambient 0.2
        
        # Base color
        base_color = np.array(self.config.face_color) / 255.0
        
        # Apply intensity to base color for each face
        # shape: (N, 3)
        face_colors = np.outer(intensity, base_color)
        
        # Ensure alpha is handled if provided in config, otherwise 1.0
        alpha = self.config.face_opacity
        
        poly = Poly3DCollection(
            triangles,
            alpha=alpha,
            facecolors=face_colors,
            edgecolor=np.array(self.config.edge_color) / 255.0,
            linewidth=0.1,
            shade=False # We computed our own shading
        )
        ax.add_collection3d(poly)
        
        # Set view angle
        elev = math.degrees(math.atan2(look_from[2], math.sqrt(look_from[0]**2 + look_from[1]**2)))
        azim = math.degrees(math.atan2(look_from[1], look_from[0]))
        ax.view_init(elev=elev, azim=azim)
        
        # Set axis limits
        bounds = mesh.bounds
        max_range = np.max(bounds[1] - bounds[0]) / 2
        # center calculated above
        ax.set_xlim(center[0] - max_range, center[0] + max_range)
        ax.set_ylim(center[1] - max_range, center[1] + max_range)
        ax.set_zlim(center[2] - max_range, center[2] + max_range)
        
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_zlabel('Z (mm)')
        # ax.set_title(f'{view.upper()} view') # Title block handles metadata now
        
        # Remove background/grid for cleaner look if requested
        if not self.config.show_grid:
            ax.grid(False)
            ax.xaxis.pane.fill = False
            ax.yaxis.pane.fill = False
            ax.zaxis.pane.fill = False
            ax.xaxis.pane.set_edgecolor('w')
            ax.yaxis.pane.set_edgecolor('w')
            ax.zaxis.pane.set_edgecolor('w')
            
        if not self.config.show_axes:
            ax.set_axis_off()
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=100, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close()
        
        return output_path
    
    def _drawing_to_svg(self, drawing: Any, shape: Any, 
                        view: ViewAngle, with_dimensions: bool,
                        metadata: dict = None) -> str:
        """Convert a build123d Drawing to SVG string with dimensions."""
        import svgwrite
        
        # Get bounding box of visible lines
        all_edges = []
        bb_min = np.array([float('inf'), float('inf')])
        bb_max = np.array([float('-inf'), float('-inf')])
        
        def process_edges(compound, is_hidden=False):
            nonlocal bb_min, bb_max
            if compound is None:
                return []
            edges = []
            try:
                for edge in compound.edges():
                    points = []
                    for i in range(21):
                        t = i / 20.0
                        try:
                            pt = edge.position_at(t)
                            points.append((pt.X, -pt.Y))  # Flip Y for SVG
                            bb_min = np.minimum(bb_min, [pt.X, -pt.Y])
                            bb_max = np.maximum(bb_max, [pt.X, -pt.Y])
                        except Exception:
                            pass
                    if len(points) > 1:
                        edges.append({"points": points, "hidden": is_hidden})
            except Exception:
                pass
            return edges
        
        visible_edges = process_edges(drawing.visible_lines, False)
        hidden_edges = process_edges(drawing.hidden_lines, True)
        all_edges = visible_edges + hidden_edges
        
        if bb_min[0] == float('inf'):
            # No edges - return empty SVG
            return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"></svg>'
        
        # Calculate scale and offset
        margin = self.config.margin
        drawing_width = bb_max[0] - bb_min[0]
        drawing_height = bb_max[1] - bb_min[1]
        
        if drawing_width == 0 or drawing_height == 0:
            scale = 1.0
        else:
            scale_x = (self.config.width - 2 * margin) / drawing_width
            scale_y = (self.config.height - 2 * margin) / drawing_height
            scale = min(scale_x, scale_y)
        
        offset_x = margin + (self.config.width - 2 * margin - drawing_width * scale) / 2
        offset_y = margin + (self.config.height - 2 * margin - drawing_height * scale) / 2
        
        def transform(pt):
            return (
                (pt[0] - bb_min[0]) * scale + offset_x,
                (pt[1] - bb_min[1]) * scale + offset_y,
            )
        
        # Create SVG
        dwg = svgwrite.Drawing(size=(self.config.width, self.config.height))
        dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), fill='white'))
        
        # Draw edges
        for edge_data in all_edges:
            points = [transform(p) for p in edge_data["points"]]
            if edge_data["hidden"]:
                color = f"rgb{self.config.hidden_color}"
                width = self.config.hidden_line_width
                dasharray = "4,3"
            else:
                color = f"rgb{self.config.edge_color}"
                width = self.config.line_width
                dasharray = None
            
            polyline = dwg.polyline(
                points=points,
                stroke=color,
                stroke_width=width,
                fill='none'
            )
            if dasharray:
                polyline['stroke-dasharray'] = dasharray
            dwg.add(polyline)
        
        # Add dimensions if requested
        if with_dimensions and self.config.show_dimensions:
            self._add_svg_dimensions(dwg, shape, view, scale, bb_min, offset_x, offset_y)
        
        # Add view label
        dwg.add(dwg.text(
            view.upper(),
            insert=(10, self.config.height - 10),
            font_size='14px',
            font_family='monospace',
            fill='gray'
        ))
        
        # Add title block if metadata is provided
        if metadata is not None:
            self._add_title_block(dwg, metadata, scale)
        
        return dwg.tostring()
    
    def _add_svg_dimensions(self, dwg, shape, view, scale, bb_min, offset_x, offset_y):
        """Add dimension annotations to SVG with proper engineering-style arrows."""
        try:
            bb = shape.bounding_box()
            
            # Get dimensions based on view
            if view in ("front", "back"):
                dim_h = abs(bb.max.X - bb.min.X)  # Width
                dim_v = abs(bb.max.Z - bb.min.Z)  # Height
            elif view in ("right", "left"):
                dim_h = abs(bb.max.Y - bb.min.Y)  # Depth
                dim_v = abs(bb.max.Z - bb.min.Z)  # Height
            elif view in ("top", "bottom"):
                dim_h = abs(bb.max.X - bb.min.X)  # Width
                dim_v = abs(bb.max.Y - bb.min.Y)  # Depth
            else:
                return  # No dimensions for iso views
            
            margin = self.config.margin
            w, h = self.config.width, self.config.height
            
            def draw_dimension_h(y, x1, x2, label, color='red'):
                """Draw horizontal dimension with arrows."""
                # Extension lines
                dwg.add(dwg.line(start=(x1, y-8), end=(x1, y+3), stroke=color, stroke_width=0.5))
                dwg.add(dwg.line(start=(x2, y-8), end=(x2, y+3), stroke=color, stroke_width=0.5))
                # Dimension line
                dwg.add(dwg.line(start=(x1, y), end=(x2, y), stroke=color, stroke_width=0.8))
                # Arrows (triangles)
                arrow_size = 4
                dwg.add(dwg.polygon(
                    points=[(x1, y), (x1+arrow_size, y-2), (x1+arrow_size, y+2)],
                    fill=color
                ))
                dwg.add(dwg.polygon(
                    points=[(x2, y), (x2-arrow_size, y-2), (x2-arrow_size, y+2)],
                    fill=color
                ))
                # Label
                dwg.add(dwg.text(
                    label, insert=((x1+x2)/2, y-4),
                    text_anchor='middle', font_size='11px',
                    font_family='monospace', fill=color
                ))
            
            def draw_dimension_v(x, y1, y2, label, color='blue'):
                """Draw vertical dimension with arrows."""
                # Extension lines
                dwg.add(dwg.line(start=(x-8, y1), end=(x+3, y1), stroke=color, stroke_width=0.5))
                dwg.add(dwg.line(start=(x-8, y2), end=(x+3, y2), stroke=color, stroke_width=0.5))
                # Dimension line
                dwg.add(dwg.line(start=(x, y1), end=(x, y2), stroke=color, stroke_width=0.8))
                # Arrows
                arrow_size = 4
                dwg.add(dwg.polygon(
                    points=[(x, y1), (x-2, y1+arrow_size), (x+2, y1+arrow_size)],
                    fill=color
                ))
                dwg.add(dwg.polygon(
                    points=[(x, y2), (x-2, y2-arrow_size), (x+2, y2-arrow_size)],
                    fill=color
                ))
                # Label (rotated)
                dwg.add(dwg.text(
                    label, insert=(x+6, (y1+y2)/2),
                    font_size='11px', font_family='monospace', fill=color,
                    transform=f"rotate(90, {x+6}, {(y1+y2)/2})"
                ))
            
            # Overall horizontal dimension (bottom)
            y_dim = h - margin // 3
            x_start = offset_x
            x_end = offset_x + dim_h * scale
            draw_dimension_h(y_dim, x_start, x_end, f"{dim_h:.1f} mm")
            
            # Overall vertical dimension (right side)
            x_dim = w - margin // 3
            y_start = offset_y
            y_end = offset_y + dim_v * scale
            draw_dimension_v(x_dim, y_start, y_end, f"{dim_v:.1f} mm")
            
            # Try to add feature dimensions from dimensioner
            try:
                from src.dimensioner import Dimensioner
                dimensioner = Dimensioner()
                dims = dimensioner._cylindrical_dimensions(shape)
                
                for dim in dims[:3]:  # Max 3 diameter annotations
                    # Project the dimension center to the current view
                    cx, cy, cz = dim.start
                    if view in ("front", "back"):
                        px = (cx - bb.min.X) * scale + offset_x
                        py = (bb.max.Z - cz) * scale + offset_y  # Flip Z
                    elif view in ("right", "left"):
                        px = (cy - bb.min.Y) * scale + offset_x
                        py = (bb.max.Z - cz) * scale + offset_y
                    elif view in ("top", "bottom"):
                        px = (cx - bb.min.X) * scale + offset_x
                        py = (cy - bb.min.Y) * scale + offset_y
                    else:
                        continue
                    
                    # Draw diameter annotation
                    r_px = dim.value / 2 * scale
                    dwg.add(dwg.circle(
                        center=(px, py), r=r_px,
                        stroke='green', stroke_width=0.5, fill='none',
                        stroke_dasharray='2,2'
                    ))
                    dwg.add(dwg.text(
                        dim.label, insert=(px + r_px + 3, py),
                        font_size='10px', font_family='monospace', fill='green'
                    ))
            except Exception:
                pass  # Feature dimensions are optional
            
        except Exception as e:
            print(f"Dimension annotation failed: {e}")
            import traceback
            traceback.print_exc()

    def _add_title_block(self, dwg, metadata: dict, scale_val: float):
        """Add an engineering title block to the SVG."""
        import datetime
        
        # Defaults
        title = metadata.get('title', 'Untitled')
        part_no = metadata.get('part_number', '-')
        company = metadata.get('company', 'opago GmbH')
        date_str = metadata.get('date', datetime.date.today().strftime('%Y-%m-%d'))
        drawn_by = metadata.get('drawn_by', '')
        
        # If scale is not provided in metadata, format the calculated scale
        scale_str = metadata.get('scale', f"Fit ({scale_val:.2f}x)")
        
        # Layout configuration
        w, h = self.config.width, self.config.height
        margin = self.config.margin
        
        block_w = 280
        block_h = 100
        
        x = w - margin - block_w
        y = h - margin - block_h
        
        # Main border
        dwg.add(dwg.rect(insert=(x, y), size=(block_w, block_h),
                         fill='white', stroke='black', stroke_width=1))
        
        # Inner lines
        # Horizontal divider
        dwg.add(dwg.line(start=(x, y + 60), end=(x + block_w, y + 60), stroke='black', stroke_width=0.5))
        
        # Vertical dividers
        # Company / Scale section
        dwg.add(dwg.line(start=(x + 180, y), end=(x + 180, y + 60), stroke='black', stroke_width=0.5))
        
        # Details section (bottom)
        dwg.add(dwg.line(start=(x + 100, y + 60), end=(x + 100, y + 100), stroke='black', stroke_width=0.5))
        dwg.add(dwg.line(start=(x + 190, y + 60), end=(x + 190, y + 100), stroke='black', stroke_width=0.5))
        
        # Helper for text
        def add_text(text, px, py, size='12px', weight='normal', anchor='start'):
            dwg.add(dwg.text(str(text), insert=(px, py), font_size=size,
                             font_family='monospace', font_weight=weight, text_anchor=anchor, fill='black'))
                             
        def add_label(label, px, py):
             dwg.add(dwg.text(label, insert=(px, py), font_size='9px',
                             font_family='sans-serif', fill='gray'))

        # Title (Top Left)
        add_label("TITLE", x + 5, y + 12)
        add_text(title, x + 5, y + 35, size='16px', weight='bold')
        
        # Part Number (Top Left, under Title)
        add_label("PART NO", x + 5, y + 48)
        add_text(part_no, x + 55, y + 50, size='12px')

        # Company (Top Right)
        add_label("COMPANY", x + 185, y + 12)
        add_text(company, x + 185, y + 30, size='12px')
        
        # Scale (Top Right, under Company)
        add_label("SCALE", x + 185, y + 48)
        add_text(scale_str, x + 225, y + 50, size='12px')
        
        # Bottom row: Drawn By | Date | Sheet (omitted for now)
        
        # Drawn By
        add_label("DRAWN BY", x + 5, y + 72)
        add_text(drawn_by, x + 5, y + 90, size='12px')
        
        # Date
        add_label("DATE", x + 105, y + 72)
        add_text(date_str, x + 105, y + 90, size='12px')
        
        # Sheet/Rev (Rightmost bottom)
        add_label("REV", x + 195, y + 72)
        add_text("A", x + 195, y + 90, size='12px')
    
    def _svg_to_png(self, svg_content: str, output_path: Path):
        """Convert SVG string to PNG file."""
        try:
            import cairosvg
            cairosvg.svg2png(
                bytestring=svg_content.encode('utf-8'),
                write_to=str(output_path),
                output_width=self.config.width,
                output_height=self.config.height
            )
        except ImportError:
            # Fallback: save as SVG and use PIL to create a placeholder
            svg_path = output_path.with_suffix('.svg')
            svg_path.write_text(svg_content)
            
            # Create a basic PNG from the SVG using PIL (limited)
            img = Image.new('RGB', (self.config.width, self.config.height), 'white')
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), f"SVG saved to: {svg_path.name}", fill='black')
            img.save(output_path)
    
    def _compose_multiview(self, view_images: list[tuple[str, Image.Image]]) -> Image.Image:
        """Compose multiple view images into a standard engineering layout."""
        n = len(view_images)
        
        if n <= 2:
            cols, rows = n, 1
        elif n <= 4:
            cols, rows = 2, 2
        elif n <= 6:
            cols, rows = 3, 2
        else:
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
        
        cell_w = self.config.width // cols
        cell_h = self.config.height // rows
        total_w = cell_w * cols
        total_h = cell_h * rows
        
        composed = Image.new('RGBA', (total_w, total_h), self.config.background_color)
        
        for idx, (view_name, img) in enumerate(view_images):
            row = idx // cols
            col = idx % cols
            
            # Resize maintaining aspect ratio
            img_resized = img.copy()
            img_resized.thumbnail((cell_w - 10, cell_h - 10), Image.Resampling.LANCZOS)
            
            # Center in cell
            x = col * cell_w + (cell_w - img_resized.width) // 2
            y = row * cell_h + (cell_h - img_resized.height) // 2
            
            composed.paste(img_resized, (x, y))
            
            # Add border and label
            draw = ImageDraw.Draw(composed)
            draw.rectangle(
                [col * cell_w, row * cell_h, (col + 1) * cell_w - 1, (row + 1) * cell_h - 1],
                outline=(200, 200, 200), width=1
            )
            draw.text((col * cell_w + 5, row * cell_h + 5), view_name.upper(),
                     fill=(100, 100, 100))
        
        return composed
    
    def _shape_to_trimesh(self, shape: Any):
        """Convert build123d shape to trimesh via STL export."""
        import trimesh
        from build123d import export_stl
        
        # Export to temp STL
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            tmp_path = f.name
        
        export_stl(shape, tmp_path)
        mesh = trimesh.load(tmp_path)
        
        Path(tmp_path).unlink(missing_ok=True)
        
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(mesh.dump())
        
        return mesh
    
    def _look_at_matrix(self, eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
        """Create a 4x4 look-at transformation matrix."""
        forward = target - eye
        forward = forward / np.linalg.norm(forward)
        
        right = np.cross(forward, up)
        if np.linalg.norm(right) < 1e-6:
            up = np.array([0, 1, 0])
            right = np.cross(forward, up)
        right = right / np.linalg.norm(right)
        
        true_up = np.cross(right, forward)
        
        mat = np.eye(4)
        mat[:3, 0] = right
        mat[:3, 1] = true_up
        mat[:3, 2] = -forward
        mat[:3, 3] = eye
        
        return mat
    
    def _add_label(self, img: Image.Image, text: str):
        """Add a text label to an image."""
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 
                                     self.config.font_size)
        except Exception:
            font = ImageFont.load_default()
        draw.text((10, img.height - 25), text, fill=(100, 100, 100), font=font)
