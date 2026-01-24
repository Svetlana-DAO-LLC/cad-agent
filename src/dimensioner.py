"""
CAD Dimensioner - Automatic dimension extraction and annotation.

Analyzes build123d shapes to extract meaningful dimensions:
- Overall bounding box dimensions
- Feature dimensions (holes, fillets, chamfers)
- Distance between features
- Angles
- Radii
"""

import math
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class Dimension:
    """A single dimension measurement."""
    type: str  # "linear", "radial", "angular", "diameter"
    value: float  # in mm or degrees
    label: str
    start: tuple  # 3D point
    end: tuple  # 3D point (for linear) or center (for radial)
    normal: tuple = (0, 0, 1)  # viewing direction where this dimension is visible
    

class Dimensioner:
    """Extract meaningful dimensions from build123d shapes."""
    
    def analyze(self, shape: Any) -> list[Dimension]:
        """Extract all meaningful dimensions from a shape."""
        dimensions = []
        
        # Overall bounding box dimensions
        dimensions.extend(self._bbox_dimensions(shape))
        
        # Cylindrical features (holes, bosses)
        dimensions.extend(self._cylindrical_dimensions(shape))
        
        # Fillet/chamfer radii
        dimensions.extend(self._fillet_dimensions(shape))
        
        # Edge lengths for key features
        dimensions.extend(self._key_edge_dimensions(shape))
        
        return dimensions
    
    def _bbox_dimensions(self, shape: Any) -> list[Dimension]:
        """Extract bounding box dimensions."""
        try:
            bb = shape.bounding_box()
            dims = []
            
            width = abs(bb.max.X - bb.min.X)
            depth = abs(bb.max.Y - bb.min.Y)
            height = abs(bb.max.Z - bb.min.Z)
            
            if width > 0.01:
                dims.append(Dimension(
                    type="linear", value=round(width, 2),
                    label=f"{width:.1f}",
                    start=(bb.min.X, bb.min.Y, bb.min.Z),
                    end=(bb.max.X, bb.min.Y, bb.min.Z),
                    normal=(0, -1, 0)  # visible from front
                ))
            
            if depth > 0.01:
                dims.append(Dimension(
                    type="linear", value=round(depth, 2),
                    label=f"{depth:.1f}",
                    start=(bb.min.X, bb.min.Y, bb.min.Z),
                    end=(bb.min.X, bb.max.Y, bb.min.Z),
                    normal=(-1, 0, 0)  # visible from right
                ))
            
            if height > 0.01:
                dims.append(Dimension(
                    type="linear", value=round(height, 2),
                    label=f"{height:.1f}",
                    start=(bb.min.X, bb.min.Y, bb.min.Z),
                    end=(bb.min.X, bb.min.Y, bb.max.Z),
                    normal=(0, -1, 0)  # visible from front
                ))
            
            return dims
        except Exception:
            return []
    
    def _cylindrical_dimensions(self, shape: Any) -> list[Dimension]:
        """Find cylindrical faces (holes, bosses) and extract diameters."""
        dims = []
        try:
            from build123d import GeomType
            
            cylindrical_faces = shape.faces().filter_by(GeomType.CYLINDER)
            
            seen_radii = set()
            for face in cylindrical_faces:
                try:
                    # Get the cylinder radius
                    surface = face.geom_adaptor()
                    if hasattr(surface, 'Cylinder'):
                        cyl = surface.Cylinder()
                        radius = round(cyl.Radius(), 2)
                        
                        if radius not in seen_radii:
                            seen_radii.add(radius)
                            center = face.center()
                            dims.append(Dimension(
                                type="diameter",
                                value=round(radius * 2, 2),
                                label=f"⌀{radius * 2:.1f}",
                                start=(center.X, center.Y, center.Z),
                                end=(center.X + radius, center.Y, center.Z),
                                normal=(0, 0, 1)  # visible from top
                            ))
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return dims
    
    def _fillet_dimensions(self, shape: Any) -> list[Dimension]:
        """Find filleted edges and extract radii."""
        dims = []
        try:
            from build123d import GeomType
            
            # Look for circular edges that might be fillets
            circular_edges = shape.edges().filter_by(GeomType.CIRCLE)
            
            seen_radii = set()
            for edge in circular_edges[:5]:  # Limit to avoid clutter
                try:
                    radius = round(edge.radius, 2)
                    if radius not in seen_radii and radius < 50:  # Skip large arcs
                        seen_radii.add(radius)
                        center = edge.center()
                        dims.append(Dimension(
                            type="radial",
                            value=radius,
                            label=f"R{radius:.1f}",
                            start=(center.X, center.Y, center.Z),
                            end=(center.X + radius, center.Y, center.Z),
                        ))
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return dims
    
    def _key_edge_dimensions(self, shape: Any) -> list[Dimension]:
        """Extract dimensions of key edges (longest, shortest, etc.)."""
        dims = []
        try:
            from build123d import GeomType
            
            linear_edges = shape.edges().filter_by(GeomType.LINE)
            if not linear_edges:
                return dims
            
            # Get unique edge lengths
            lengths = {}
            for edge in linear_edges:
                try:
                    length = round(edge.length, 1)
                    if length > 0.1:
                        if length not in lengths:
                            start = edge.position_at(0)
                            end = edge.position_at(1)
                            lengths[length] = (start, end)
                except Exception:
                    continue
            
            # Report unique lengths (deduplicated by value)
            for length, (start, end) in sorted(lengths.items(), reverse=True)[:8]:
                # Determine the edge direction for the normal
                dx = abs(end.X - start.X)
                dy = abs(end.Y - start.Y)
                dz = abs(end.Z - start.Z)
                
                # Choose a viewing normal perpendicular to the edge
                if dz > dx and dz > dy:
                    normal = (0, -1, 0)  # vertical edge, view from front
                elif dx > dy:
                    normal = (0, -1, 0)  # horizontal X edge, view from front
                else:
                    normal = (-1, 0, 0)  # horizontal Y edge, view from right
                
                dims.append(Dimension(
                    type="linear",
                    value=length,
                    label=f"{length:.1f}",
                    start=(start.X, start.Y, start.Z),
                    end=(end.X, end.Y, end.Z),
                    normal=normal
                ))
        except Exception:
            pass
        
        return dims
    
    def get_dimension_summary(self, shape: Any) -> dict:
        """Get a text summary of all dimensions."""
        dims = self.analyze(shape)
        
        summary = {
            "overall": {},
            "features": [],
            "all_dimensions": []
        }
        
        for d in dims:
            entry = {
                "type": d.type,
                "value_mm": d.value if d.type != "angular" else None,
                "value_deg": d.value if d.type == "angular" else None,
                "label": d.label,
            }
            summary["all_dimensions"].append(entry)
            
            if d.type == "linear" and d.label in [f"{d.value:.1f}"]:
                # Bounding box dims
                summary["overall"][d.label] = d.value
            elif d.type in ("diameter", "radial"):
                summary["features"].append(entry)
        
        return summary
