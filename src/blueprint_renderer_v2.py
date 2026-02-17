"""
Blueprint Renderer - Enhanced 2D Technical Drawing Generation

Improvements:
- ANSI/ISO engineering drawing standards
- Better dimension placement algorithms  
- Tolerance annotations
- Section views
- Improved measurement accuracy

Author: Svetlana DAO
License: PolyForm Small Business License 1.0.0
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, Polygon, Arc
from matplotlib.lines import Line2D
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
    Enhanced 2D technical blueprints with ANSI/ISO standards.
    """
    
    def __init__(self, output_dir: str = "/renders"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # ANSI-style drawing defaults
        self.style = {
            'outline_color': '#000080',  # Navy blue (ANSI)
            'outline_width': 1.5,
            'fill_alpha': 0.15,
            'dim_color': '#FF0000',  # Red for dimensions
            'dim_line_color': '#FF0000',
            'center_line_color': '#0000FF',
            'hidden_line_color': '#808080',
            'dim_fontsize': 9,
            'title_fontsize': 14,
            'suptitle_fontsize': 16,
            'tol_fontsize': 7,
            'grid_alpha': 0.2,
            'sheet_size': 'A4',  # A4 or A3
            'scale': 1.0,
            'units': 'mm',  # mm or inch
        }
        
        # Sheet sizes (mm)
        self.sheet_sizes = {
            'A4': (210, 297),
            'A3': (297, 420),
            'Letter': (215.9, 279.4),
        }
    
    def _get_sheet_size(self) -> Tuple[float, float]:
        """Get sheet size in mm."""
        return self.sheet_sizes.get(self.style['sheet_size'], self.sheet_sizes['A4'])
    
    def _draw_dimension_arrow(self, ax, start: Tuple[float, float], 
                             end: Tuple[float, float], 
                             offset: float = 5,
                             label: str = "",
                             tolerance: str = ""):
        """Draw ANSI-style dimension with proper arrows."""
        # Calculate direction
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = np.sqrt(dx**2 + dy**2)
        
        if length < 0.001:
            return
        
        # Normalize
        ux, uy = dx/length, dy/length
        
        # Offset perpendicular to dimension line
        ox, oy = -uy * offset, ux * offset
        
        # Draw extension lines
        ax.plot([start[0] - ux*3, start[0]], [start[1] - uy*3, start[1]], 
                color=self.style['dim_line_color'], linewidth=0.7)
        ax.plot([end[0], end[0] + ux*3], [end[1], end[1] + uy*3], 
                color=self.style['dim_line_color'], linewidth=0.7)
        
        # Draw dimension line
        ax.plot([start[0] + ox, end[0] + ox], [start[1] + oy, end[1] + oy],
                color=self.style['dim_line_color'], linewidth=0.8)
        
        # Draw arrows at ends
        arrow_size = 3
        for x, y in [(start[0] + ox, start[1] + oy), (end[0] + ox, end[1] + oy)]:
            ax.annotate('', xy=(x + ux*arrow_size, y + uy*arrow_size),
                       xytext=(x, y),
                       arrowprops=dict(arrowstyle='->', color=self.style['dim_line_color'],
                                     lw=0.8))
        
        # Draw label
        mid_x = (start[0] + end[0]) / 2 + ox
        mid_y = (start[1] + end[1]) / 2 + oy
        
        if label:
            ax.text(mid_x, mid_y, label, fontsize=self.style['dim_fontsize'],
                   color=self.style['dim_color'], ha='center', va='center',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                           edgecolor='none', alpha=0.8))
        
        # Draw tolerance if provided
        if tolerance:
            tol_y = mid_y - 4
            ax.text(mid_x, tol_y, tolerance, fontsize=self.style['tol_fontsize'],
                   color=self.style['dim_color'], ha='center', va='top')
    
    def _draw_radius_dimension(self, ax, center: Tuple[float, float], 
                              radius: float, label: str = "R"):
        """Draw radius dimension (ANSI style)."""
        # Draw radius line from center to arc
        ax.plot([center[0], center[0] + radius], [center[1], center[1]],
                color=self.style['dim_line_color'], linewidth=0.8)
        
        # Draw arrow
        ax.annotate('', xy=(center[0] + radius - 2, center[1] + 1),
                   xytext=(center[0] + radius, center[1]),
                   arrowprops=dict(arrowstyle='->', color=self.style['dim_line_color'], lw=0.8))
        
        # Draw label
        ax.text(center[0] + radius/2, center[1] + 3, f"{label}{radius:.1f}",
               fontsize=self.style['dim_fontsize'], color=self.style['dim_color'],
               ha='center', va='bottom')
    
    def _draw_diameter_dimension(self, ax, center: Tuple[float, float],
                                diameter: float, label: str = "⌀"):
        """Draw diameter dimension (ANSI style)."""
        # Draw center lines
        cl = diameter * 0.15
        ax.plot([center[0] - cl, center[0] + cl], [center[1], center[1]],
                color=self.style['center_line_color'], linewidth=0.5, linestyle='--')
        ax.plot([center[0], center[0]], [center[1] - cl, center[1] + cl],
                color=self.style['center_line_color'], linewidth=0.5, linestyle='--')
        
        # Draw dimension outside
        offset = diameter/2 + 8
        ax.text(center[0] + offset, center[1], f"⌀{diameter:.1f}",
               fontsize=self.style['dim_fontsize'], color=self.style['dim_color'],
               ha='left', va='center')
    
    def _draw_center_mark(self, ax, center: Tuple[float, float], size: float = 5):
        """Draw center mark for symmetric features."""
        ax.plot([center[0] - size, center[0] + size], [center[1], center[1]],
                color=self.style['center_line_color'], linewidth=0.5)
        ax.plot([center[0], center[0]], [center[1] - size, center[1] + size],
                color=self.style['center_line_color'], linewidth=0.5)
    
    def render_ansi_view(self, shape, view: str = "front", 
                        filename: str = "blueprint.png",
                        title: str = "PART",
                        with_dimensions: bool = True,
                        with_tolerances: bool = True) -> Path:
        """
        Render an ANSI-standard orthographic view.
        
        Args:
            shape: build123d or trimesh object
            view: 'front', 'top', 'right', 'left', 'bottom', 'back', 'iso'
            filename: output filename
            title: part title
            with_dimensions: show dimensions
            with_tolerances: show tolerances (if with_dimensions)
        """
        dims = self.extract_dimensions(shape)
        
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))
        
        # Set up the view based on type
        if view == 'front':
            self._render_front_view_ansi(ax, dims, title)
        elif view == 'top':
            self._render_top_view_ansi(ax, dims, title)
        elif view == 'right' or view == 'side':
            self._render_side_view_ansi(ax, dims, title)
        
        # Add title block (ANSI style)
        self._draw_title_block(fig, title)
        
        # Add dimensions if requested
        if with_dimensions:
            self._add_dimensions_ansi(ax, dims, view, with_tolerances)
        
        # Save
        path = self.output_dir / filename
        plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        return path
    
    def _render_front_view_ansi(self, ax, dims: ModelDimensions, title: str):
        """Render front view with ANSI styling."""
        w, d, h = dims.width, dims.depth, dims.height
        
        # Draw part outline
        rect = Rectangle((-w/2, 0), w, h,
                        fill=True, alpha=self.style['fill_alpha'],
                        edgecolor=self.style['outline_color'], 
                        linewidth=self.style['outline_width'],
                        facecolor='#E6E6E6')
        ax.add_patch(rect)
        
        # Add center marks
        self._draw_center_mark(ax, (0, h/2))
        self._draw_center_mark(ax, (w/2, 0))
        
        ax.set_title(title.upper(), fontsize=self.style['title_fontsize'], 
                    fontweight='bold', pad=20)
        ax.set_xlim(-w*0.5, w*1.5)
        ax.set_ylim(-h*0.3, h*1.3)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Grid
        ax.grid(True, alpha=self.style['grid_alpha'], linestyle=':', color='#CCCCCC')
    
    def _render_top_view_ansi(self, ax, dims: ModelDimensions, title: str):
        """Render top view with ANSI styling."""
        w, d, h = dims.width, dims.depth, dims.height
        
        rect = Rectangle((-w/2, -d/2), w, d,
                        fill=True, alpha=self.style['fill_alpha'],
                        edgecolor=self.style['outline_color'],
                        linewidth=self.style['outline_width'],
                        facecolor='#E6E6E6')
        ax.add_patch(rect)
        
        self._draw_center_mark(ax, (0, 0))
        
        ax.set_title("TOP VIEW", fontsize=self.style['title_fontsize'],
                    fontweight='bold', pad=20)
        ax.set_xlim(-w*0.5, w*1.5)
        ax.set_ylim(-d*0.5, d*1.5)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.grid(True, alpha=self.style['grid_alpha'], linestyle=':', color='#CCCCCC')
    
    def _render_side_view_ansi(self, ax, dims: ModelDimensions, title: str):
        """Render side view with ANSI styling."""
        w, d, h = dims.width, dims.depth, dims.height
        
        rect = Rectangle((-d/2, 0), d, h,
                        fill=True, alpha=self.style['fill_alpha'],
                        edgecolor=self.style['outline_color'],
                        linewidth=self.style['outline_width'],
                        facecolor='#E6E6E6')
        ax.add_patch(rect)
        
        self._draw_center_mark(ax, (0, h/2))
        
        ax.set_title("RIGHT SIDE VIEW", fontsize=self.style['title_fontsize'],
                    fontweight='bold', pad=20)
        ax.set_xlim(-d*0.5, d*1.5)
        ax.set_ylim(-h*0.3, h*1.3)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.grid(True, alpha=self.style['grid_alpha'], linestyle=':', color='#CCCCCC')
    
    def _add_dimensions_ansi(self, ax, dims: ModelDimensions, view: str,
                           with_tolerances: bool = True):
        """Add dimensions to ANSI view."""
        w, d, h = dims.width, dims.depth, dims.height
        
        tol = "±0.5" if with_tolerances else ""
        
        if view == 'front':
            # Width dimension
            self._draw_dimension_arrow(ax, (-w/2, -h*0.15), (w/2, -h*0.15),
                                     offset=3, label=f"{w:.1f}", tolerance=tol)
            # Height dimension
            self._draw_dimension_arrow(ax, (w/2 + w*0.1, 0), (w/2 + w*0.1, h),
                                     offset=3, label=f"{h:.1f}", tolerance=tol)
        
        elif view == 'top':
            # Width
            self._draw_dimension_arrow(ax, (-w/2, d/2 + d*0.1), (w/2, d/2 + d*0.1),
                                     offset=3, label=f"{w:.1f}", tolerance=tol)
            # Depth  
            self._draw_dimension_arrow(ax, (w/2 + w*0.1, -d/2), (w/2 + w*0.1, d/2),
                                     offset=3, label=f"{d:.1f}", tolerance=tol)
        
        elif view in ('right', 'side'):
            self._draw_dimension_arrow(ax, (-d/2, -h*0.15), (d/2, -h*0.15),
                                     offset=3, label=f"{d:.1f}", tolerance=tol)
            self._draw_dimension_arrow(ax, (d/2 + d*0.1, 0), (d/2 + d*0.1, h),
                                     offset=3, label=f"{h:.1f}", tolerance=tol)
    
    def _draw_title_block(self, fig, title: str):
        """Draw ANSI title block in bottom right."""
        ax = fig.add_axes([0.65, 0.02, 0.33, 0.12])
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 30)
        
        # Border
        ax.add_patch(Rectangle((0, 0), 100, 30, fill=False, 
                              edgecolor='black', linewidth=1))
        ax.add_patch(Rectangle((0, 0), 70, 30, fill=False, edgecolor='black', linewidth=1))
        ax.add_patch(Rectangle((70, 0), 30, 15, fill=False, edgecolor='black', linewidth=1))
        
        # Title
        ax.text(35, 20, title.upper(), fontsize=10, ha='center', va='center',
               fontweight='bold')
        ax.text(35, 8, "Svetlana DAO", fontsize=6, ha='center', va='center')
        
        # Scale
        ax.text(85, 22, "SCALE: 1:1", fontsize=6, ha='center', va='center')
        ax.text(85, 8, "MM", fontsize=6, ha='center', va='center')
        
        ax.axis('off')
    
    def extract_dimensions(self, mesh) -> ModelDimensions:
        """Extract dimensions from a mesh or build123d object."""
        if hasattr(mesh, 'bounds'):
            bounds = np.array(mesh.bounds)
        elif hasattr(mesh, 'bounding_box'):
            bb = mesh.bounding_box()
            bounds = np.array([
                [bb.min.X, bb.min.Y, bb.min.Z],
                [bb.max.X, bb.max.Y, bb.max.Z]
            ])
        else:
            bounds = np.array([[0,0,0], [10,10,10]])
        
        dims = bounds[1] - bounds[0]
        return ModelDimensions(
            width=dims[0],
            depth=dims[1],
            height=dims[2],
            bounds=bounds
        )
    
    def render_multiview_ansi(self, shape, filename: str = "multiview_ansi.png",
                             title: str = "PART") -> Path:
        """Render complete ANSI multi-view drawing."""
        dims = self.extract_dimensions(shape)
        
        fig = plt.figure(figsize=(12, 9), facecolor='white')
        
        # Title
        fig.suptitle(title.upper(), fontsize=18, fontweight='bold', y=0.98)
        
        # Front view (top left)
        ax1 = fig.add_subplot(2, 3, 1)
        self._render_front_view_ansi(ax1, dims, "FRONT")
        
        # Top view (middle)
        ax2 = fig.add_subplot(2, 3, 2)
        self._render_top_view_ansi(ax2, dims, "TOP")
        
        # Right side (top right)
        ax3 = fig.add_subplot(2, 3, 3)
        self._render_side_view_ansi(ax3, dims, "RIGHT")
        
        # Notes (bottom)
        ax4 = fig.add_subplot(2, 3, (4, 6))
        ax4.axis('off')
        ax4.text(0.5, 0.8, "NOTES:", fontsize=10, fontweight='bold', 
                ha='center', transform=ax4.transAxes)
        ax4.text(0.5, 0.6, "1. All dimensions in millimeters", fontsize=9,
                ha='center', transform=ax4.transAxes)
        ax4.text(0.5, 0.5, "2. Tolerances unless otherwise specified: ±0.5mm", fontsize=9,
                ha='center', transform=ax4.transAxes)
        ax4.text(0.5, 0.4, "3. Remove all sharp edges 0.3mm max", fontsize=9,
                ha='center', transform=ax4.transAxes)
        
        # Title block
        self._draw_title_block(fig, title)
        
        path = self.output_dir / filename
        plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        return path


# Backward compatibility
class EnhancedBlueprintRenderer(BlueprintRenderer):
    """Alias for BlueprintRenderer."""
    pass
