"""
Blueprint Renderer - 2D Technical Drawing Generation using Matplotlib

Generates proper orthographic 2D technical drawings with dimensions,
replacing the HLR-based approach which times out on STL meshes.

Author: Svetlana (Clawdbot) for Svetlana DAO LLC
License: PolyForm Small Business License 1.0.0
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, Polygon
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import numpy as np


@dataclass
class ModelDimensions:
    """Extracted dimensions from a 3D model."""
    width: float   # X dimension
    depth: float   # Y dimension  
    height: float  # Z dimension
    bounds: np.ndarray  # [[min_x, min_y, min_z], [max_x, max_y, max_z]]


class BlueprintRenderer:
    """
    Generates 2D technical blueprints from 3D models using matplotlib.
    
    Creates orthographic projections (front, side, top, bottom) with
    dimension annotations in engineering drawing style.
    """
    
    def __init__(self, output_dir: str = "/renders"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Default styling
        self.style = {
            'outline_color': 'blue',
            'outline_width': 2,
            'fill_alpha': 0.2,
            'dim_color': 'red',
            'dim_fontsize': 11,
            'grid_alpha': 0.3,
            'title_fontsize': 12,
            'suptitle_fontsize': 16,
        }
    
    def extract_dimensions(self, mesh) -> ModelDimensions:
        """Extract dimensions from a trimesh or build123d object."""
        if hasattr(mesh, 'bounds'):
            bounds = np.array(mesh.bounds)
        elif hasattr(mesh, 'bounding_box'):
            bb = mesh.bounding_box()
            bounds = np.array([
                [bb.min.X, bb.min.Y, bb.min.Z],
                [bb.max.X, bb.max.Y, bb.max.Z]
            ])
        else:
            raise ValueError("Cannot extract bounds from object")
        
        dims = bounds[1] - bounds[0]
        return ModelDimensions(
            width=dims[0],
            depth=dims[1],
            height=dims[2],
            bounds=bounds
        )
    
    def render_profile_view(self, ax: plt.Axes, profile_points: List[Tuple[float, float]],
                           title: str = "PROFILE VIEW", dims: Dict[str, Any] = None):
        """Render a 2D profile view with optional dimensions."""
        ax.set_title(title, fontsize=self.style['title_fontsize'], fontweight='bold')
        
        # Draw profile
        x = [p[0] for p in profile_points]
        y = [p[1] for p in profile_points]
        ax.plot(x + [x[0]], y + [y[0]], color=self.style['outline_color'], 
                linewidth=self.style['outline_width'])
        ax.fill(x, y, alpha=self.style['fill_alpha'], color=self.style['outline_color'])
        
        # Add dimensions if provided
        if dims:
            self._add_dimensions(ax, dims)
        
        ax.set_aspect('equal')
        ax.grid(True, alpha=self.style['grid_alpha'], linestyle='--')
    
    def render_rect_view(self, ax: plt.Axes, width: float, height: float,
                        title: str = "VIEW", corner_radius: float = 0,
                        center: Tuple[float, float] = (0, 0),
                        dims: Dict[str, Any] = None):
        """Render a rectangular view (top, front, side)."""
        ax.set_title(title, fontsize=self.style['title_fontsize'], fontweight='bold')
        
        cx, cy = center
        if corner_radius > 0:
            rect = FancyBboxPatch(
                (cx - width/2, cy - height/2), width, height,
                boxstyle=f'round,pad=0,rounding_size={corner_radius}',
                fill=True, alpha=self.style['fill_alpha'],
                edgecolor=self.style['outline_color'],
                linewidth=self.style['outline_width'],
                facecolor='lightblue'
            )
        else:
            rect = Rectangle(
                (cx - width/2, cy - height/2), width, height,
                fill=True, alpha=self.style['fill_alpha'],
                edgecolor=self.style['outline_color'],
                linewidth=self.style['outline_width'],
                facecolor='lightblue'
            )
        ax.add_patch(rect)
        
        if dims:
            self._add_dimensions(ax, dims)
        
        ax.set_aspect('equal')
        ax.grid(True, alpha=self.style['grid_alpha'], linestyle='--')
    
    def _add_dimensions(self, ax: plt.Axes, dims: Dict[str, Any]):
        """Add dimension annotations to an axis."""
        for dim in dims.get('arrows', []):
            ax.annotate('', 
                xy=dim['end'], xytext=dim['start'],
                arrowprops=dict(arrowstyle='<->', color=dim.get('color', self.style['dim_color']), lw=1.5)
            )
        
        for text in dims.get('texts', []):
            ax.text(
                text['x'], text['y'], str(text['value']),
                fontsize=text.get('fontsize', self.style['dim_fontsize']),
                color=text.get('color', self.style['dim_color']),
                ha=text.get('ha', 'center'),
                va=text.get('va', 'center'),
                fontweight=text.get('fontweight', 'bold')
            )
    
    def render_blueprint(self, mesh, filename: str = "blueprint.png",
                        title: str = "TECHNICAL DRAWING",
                        views: List[str] = None,
                        custom_specs: str = None) -> Path:
        """
        Render a complete technical blueprint with multiple orthographic views.
        
        Args:
            mesh: trimesh or build123d object
            filename: Output filename
            title: Drawing title
            views: List of views to include ['front', 'side', 'top', 'bottom']
            custom_specs: Custom specifications text
            
        Returns:
            Path to saved image
        """
        dims = self.extract_dimensions(mesh)
        
        if views is None:
            views = ['front', 'right', 'top', 'bottom']
        
        n_views = len(views)
        cols = min(n_views, 2)
        rows = (n_views + 1) // 2 + 1  # +1 for specs
        
        fig = plt.figure(figsize=(8 * cols, 6 * rows), facecolor='white')
        fig.suptitle(f'{title}\nAll dimensions in mm', 
                    fontsize=self.style['suptitle_fontsize'], fontweight='bold', y=0.98)
        
        # Create view axes
        for i, view in enumerate(views):
            ax = fig.add_subplot(rows, cols, i + 1)
            self._render_view(ax, dims, view)
        
        # Add specs panel
        ax_specs = fig.add_subplot(rows, cols, len(views) + 1)
        ax_specs.axis('off')
        ax_specs.set_title('SPECIFICATIONS', fontsize=self.style['title_fontsize'], fontweight='bold')
        
        specs = custom_specs or self._generate_specs(dims)
        ax_specs.text(0.05, 0.95, specs, transform=ax_specs.transAxes, fontsize=10,
                     verticalalignment='top', fontfamily='monospace',
                     bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', edgecolor='gray'))
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=150, facecolor='white', bbox_inches='tight')
        plt.close(fig)
        
        return output_path
    
    def _render_view(self, ax: plt.Axes, dims: ModelDimensions, view: str):
        """Render a specific orthographic view."""
        w, d, h = dims.width, dims.depth, dims.height
        
        if view == 'front':
            ax.set_title('FRONT VIEW', fontsize=self.style['title_fontsize'], fontweight='bold')
            ax.add_patch(Rectangle((-w/2, 0), w, h, fill=True, alpha=0.2,
                                   edgecolor='blue', linewidth=2, facecolor='lightblue'))
            # Width dimension
            ax.annotate('', xy=(w/2, -h*0.1), xytext=(-w/2, -h*0.1),
                       arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))
            ax.text(0, -h*0.2, f'{w:.1f}', fontsize=11, color='red', ha='center', fontweight='bold')
            # Height dimension
            ax.annotate('', xy=(w/2 + w*0.1, h), xytext=(w/2 + w*0.1, 0),
                       arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))
            ax.text(w/2 + w*0.15, h/2, f'{h:.1f}', fontsize=11, color='red', va='center', fontweight='bold')
            ax.set_xlim(-w*0.8, w*0.8)
            ax.set_ylim(-h*0.4, h*1.3)
            
        elif view == 'right' or view == 'side':
            ax.set_title('RIGHT VIEW', fontsize=self.style['title_fontsize'], fontweight='bold')
            ax.add_patch(Rectangle((-d/2, 0), d, h, fill=True, alpha=0.2,
                                   edgecolor='blue', linewidth=2, facecolor='lightblue'))
            ax.annotate('', xy=(d/2, -h*0.1), xytext=(-d/2, -h*0.1),
                       arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))
            ax.text(0, -h*0.2, f'{d:.1f}', fontsize=11, color='red', ha='center', fontweight='bold')
            ax.set_xlim(-d*0.8, d*0.8)
            ax.set_ylim(-h*0.4, h*1.3)
            
        elif view == 'top':
            ax.set_title('TOP VIEW', fontsize=self.style['title_fontsize'], fontweight='bold')
            ax.add_patch(Rectangle((-w/2, -d/2), w, d, fill=True, alpha=0.2,
                                   edgecolor='blue', linewidth=2, facecolor='lightblue'))
            ax.annotate('', xy=(w/2, d/2 + d*0.1), xytext=(-w/2, d/2 + d*0.1),
                       arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))
            ax.text(0, d/2 + d*0.2, f'{w:.1f} × {d:.1f}', fontsize=11, color='red', 
                   ha='center', fontweight='bold')
            ax.set_xlim(-w*0.7, w*0.7)
            ax.set_ylim(-d*0.7, d*0.9)
            
        elif view == 'bottom':
            ax.set_title('BOTTOM VIEW', fontsize=self.style['title_fontsize'], fontweight='bold')
            ax.add_patch(Rectangle((-w/2, -d/2), w, d, fill=True, alpha=0.2,
                                   edgecolor='green', linewidth=2, facecolor='lightgreen'))
            ax.annotate('', xy=(w/2, d/2 + d*0.1), xytext=(-w/2, d/2 + d*0.1),
                       arrowprops=dict(arrowstyle='<->', color='green', lw=1.5))
            ax.text(0, d/2 + d*0.2, f'{w:.1f} × {d:.1f}', fontsize=11, color='green',
                   ha='center', fontweight='bold')
            ax.set_xlim(-w*0.7, w*0.7)
            ax.set_ylim(-d*0.7, d*0.9)
        
        ax.set_aspect('equal')
        ax.grid(True, alpha=self.style['grid_alpha'], linestyle='--')
        ax.axhline(y=0, color='k', linewidth=0.5)
        ax.axvline(x=0, color='k', linewidth=0.5)
    
    def _generate_specs(self, dims: ModelDimensions) -> str:
        """Generate default specifications text."""
        return f"""MODEL DIMENSIONS

Width (X):  {dims.width:.2f} mm
Depth (Y):  {dims.depth:.2f} mm
Height (Z): {dims.height:.2f} mm

Bounding Box:
  Min: ({dims.bounds[0][0]:.1f}, {dims.bounds[0][1]:.1f}, {dims.bounds[0][2]:.1f})
  Max: ({dims.bounds[1][0]:.1f}, {dims.bounds[1][1]:.1f}, {dims.bounds[1][2]:.1f})
"""
    
    def render_gridfinity_foot(self, filename: str = "gridfinity_foot_blueprint.png",
                               bottom: float = 35.6, mid: float = 37.2, top: float = 41.5,
                               h1: float = 0.8, h2: float = 1.8, total_h: float = 4.75,
                               r_bottom: float = 0.8, r_top: float = 3.75) -> Path:
        """
        Render a specialized Gridfinity foot blueprint.
        
        Uses exact Gridfinity specifications for the stepped profile.
        """
        fig = plt.figure(figsize=(16, 12), facecolor='white')
        fig.suptitle('GRIDFINITY FOOT - TECHNICAL DRAWING\nAll dimensions in mm', 
                    fontsize=16, fontweight='bold', y=0.98)
        
        h3 = total_h - h1 - h2
        
        # FRONT VIEW (Profile)
        ax1 = fig.add_subplot(2, 2, 1)
        ax1.set_title('FRONT VIEW (Profile)', fontsize=12, fontweight='bold')
        
        x = [-bottom/2, -mid/2, -mid/2, -top/2, top/2, mid/2, mid/2, bottom/2, -bottom/2]
        z = [0, h1, h1+h2, total_h, total_h, h1+h2, h1, 0, 0]
        ax1.plot(x, z, 'b-', linewidth=2)
        ax1.fill(x, z, alpha=0.15, color='blue')
        
        # Dimensions
        ax1.annotate('', xy=(top/2+3, total_h), xytext=(top/2+3, 0),
                    arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))
        ax1.text(top/2+5, total_h/2, f'{total_h}', fontsize=11, color='red', 
                va='center', fontweight='bold')
        
        ax1.annotate('', xy=(top/2, total_h+1.5), xytext=(-top/2, total_h+1.5),
                    arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))
        ax1.text(0, total_h+3, f'{top}', fontsize=11, color='red', ha='center', fontweight='bold')
        
        ax1.annotate('', xy=(bottom/2, -1.5), xytext=(-bottom/2, -1.5),
                    arrowprops=dict(arrowstyle='<->', color='green', lw=1.5))
        ax1.text(0, -3.5, f'{bottom}', fontsize=11, color='green', ha='center', fontweight='bold')
        
        ax1.set_xlim(-35, 40)
        ax1.set_ylim(-6, 12)
        ax1.set_aspect('equal')
        ax1.grid(True, alpha=0.3, linestyle='--')
        
        # TOP VIEW
        ax2 = fig.add_subplot(2, 2, 2)
        ax2.set_title('TOP VIEW', fontsize=12, fontweight='bold')
        rect = FancyBboxPatch((-top/2, -top/2), top, top, 
                             boxstyle=f'round,pad=0,rounding_size={r_top}',
                             fill=True, alpha=0.15, edgecolor='blue', linewidth=2, facecolor='blue')
        ax2.add_patch(rect)
        ax2.annotate('', xy=(top/2, top/2+3), xytext=(-top/2, top/2+3),
                    arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))
        ax2.text(0, top/2+5, f'{top} × {top}', fontsize=11, color='red', 
                ha='center', fontweight='bold')
        ax2.text(0, 0, f'R={r_top}', fontsize=10, ha='center', va='center', style='italic')
        ax2.set_xlim(-30, 30)
        ax2.set_ylim(-30, 35)
        ax2.set_aspect('equal')
        ax2.grid(True, alpha=0.3, linestyle='--')
        
        # BOTTOM VIEW
        ax3 = fig.add_subplot(2, 2, 3)
        ax3.set_title('BOTTOM VIEW', fontsize=12, fontweight='bold')
        rect = FancyBboxPatch((-bottom/2, -bottom/2), bottom, bottom,
                             boxstyle=f'round,pad=0,rounding_size={r_bottom}',
                             fill=True, alpha=0.15, edgecolor='green', linewidth=2, facecolor='green')
        ax3.add_patch(rect)
        ax3.annotate('', xy=(bottom/2, bottom/2+3), xytext=(-bottom/2, bottom/2+3),
                    arrowprops=dict(arrowstyle='<->', color='green', lw=1.5))
        ax3.text(0, bottom/2+5, f'{bottom} × {bottom}', fontsize=11, color='green',
                ha='center', fontweight='bold')
        ax3.text(0, 0, f'R={r_bottom}', fontsize=10, ha='center', va='center', style='italic')
        ax3.set_xlim(-25, 25)
        ax3.set_ylim(-25, 30)
        ax3.set_aspect('equal')
        ax3.grid(True, alpha=0.3, linestyle='--')
        
        # SPECS
        ax4 = fig.add_subplot(2, 2, 4)
        ax4.axis('off')
        ax4.set_title('SPECIFICATIONS', fontsize=12, fontweight='bold')
        specs = f"""GRIDFINITY FOOT PROFILE

DIMENSIONS
  Top:      {top} × {top} mm
  Bottom:   {bottom} × {bottom} mm
  Height:   {total_h} mm

PROFILE (from Z=0)
  0.0-{h1}:  45° chamfer
  {h1}-{h1+h2}:  Vertical
  {h1+h2}-{total_h}: 45° chamfer

CORNER RADII
  Bottom: R={r_bottom}mm
  Top:    R={r_top}mm

GRID
  Cell pitch: 42.0mm
  Cell size:  41.5mm
  Clearance:  0.5mm"""
        ax4.text(0.05, 0.95, specs, transform=ax4.transAxes, fontsize=11,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', edgecolor='gray'))
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=150, facecolor='white', bbox_inches='tight')
        plt.close(fig)
        
        return output_path


# Convenience function for direct use
def render_2d_blueprint(stl_path: str, output_path: str = None, title: str = None) -> str:
    """
    Render a 2D technical blueprint from an STL file.
    
    Args:
        stl_path: Path to STL file
        output_path: Optional output path (default: same dir as STL)
        title: Optional drawing title
        
    Returns:
        Path to generated PNG
    """
    import trimesh
    
    mesh = trimesh.load(stl_path)
    
    if output_path is None:
        output_path = Path(stl_path).with_suffix('.png').name.replace('.png', '_blueprint.png')
    
    if title is None:
        title = Path(stl_path).stem.upper().replace('_', ' ')
    
    renderer = BlueprintRenderer()
    result = renderer.render_blueprint(mesh, output_path, title)
    
    return str(result)
