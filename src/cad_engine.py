"""
CAD Engine - Wraps build123d for AI-driven model creation and manipulation.

Provides a sandboxed execution environment for build123d scripts,
model state management, and geometry analysis.
"""

import io
import sys
import traceback
import hashlib
import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ModelState:
    """Represents the current state of a CAD model."""
    name: str
    code: str
    shape: Any = None  # build123d Shape object
    history: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    @property
    def code_hash(self) -> str:
        return hashlib.md5(self.code.encode()).hexdigest()[:8]
    
    def to_dict(self) -> dict:
        """Serialize state (without shape object)."""
        info = {}
        if self.shape is not None:
            try:
                bb = self.shape.bounding_box()
                info = {
                    "bounding_box": {
                        "min": [bb.min.X, bb.min.Y, bb.min.Z],
                        "max": [bb.max.X, bb.max.Y, bb.max.Z],
                        "size": [bb.max.X - bb.min.X, bb.max.Y - bb.min.Y, bb.max.Z - bb.min.Z]
                    },
                    "volume": getattr(self.shape, 'volume', None),
                    "area": getattr(self.shape, 'area', None),
                }
            except Exception:
                pass
        
        return {
            "name": self.name,
            "code_hash": self.code_hash,
            "history_length": len(self.history),
            "geometry": info,
            "metadata": self.metadata,
        }


class CADEngine:
    """
    Sandboxed build123d execution engine.
    
    Manages model state, executes build123d code safely,
    and provides geometry analysis tools.
    """
    
    def __init__(self, workspace: Path = Path("/workspace")):
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.models: dict[str, ModelState] = {}
        self.active_model: Optional[str] = None
    
    def execute_code(self, code: str, model_name: str = "default") -> dict:
        """
        Execute build123d code in a sandboxed namespace.
        
        Returns dict with: success, result_shape, output, error, geometry_info
        """
        # Capture stdout/stderr
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        
        namespace = self._build_namespace()
        result = {"success": False, "output": "", "error": "", "geometry": None}
        
        try:
            exec(code, namespace)
            
            # Find the resulting shape(s) in namespace
            shape = self._extract_shape(namespace)
            
            if shape is not None:
                # Store model state
                state = ModelState(
                    name=model_name,
                    code=code,
                    shape=shape,
                    metadata={"source": "execute_code"}
                )
                if model_name in self.models:
                    state.history = self.models[model_name].history + [self.models[model_name].code]
                
                self.models[model_name] = state
                self.active_model = model_name
                
                result["success"] = True
                result["geometry"] = state.to_dict()["geometry"]
            else:
                result["success"] = True
                result["geometry"] = None
                result["output"] += "\n[Warning: No 3D shape found in result. Assign to 'result' variable.]"
            
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        
        finally:
            result["output"] = sys.stdout.getvalue()
            if sys.stderr.getvalue():
                result["error"] = sys.stderr.getvalue() + "\n" + result.get("error", "")
            sys.stdout, sys.stderr = old_stdout, old_stderr
        
        return result
    
    def _build_namespace(self) -> dict:
        """Build the execution namespace with build123d imports."""
        namespace = {"__builtins__": __builtins__}
        
        # Import build123d into namespace
        try:
            exec("from build123d import *", namespace)
        except ImportError as e:
            raise RuntimeError(f"build123d not available: {e}")
        
        # Add numpy for parametric work
        namespace["np"] = np
        namespace["numpy"] = np
        
        # Add reference to existing models
        namespace["_models"] = {
            name: state.shape for name, state in self.models.items()
            if state.shape is not None
        }
        
        return namespace
    
    def _extract_shape(self, namespace: dict) -> Any:
        """Extract the resulting shape from the execution namespace."""
        # Priority: explicit 'result' variable, then any Part/Solid/Compound
        if "result" in namespace and namespace["result"] is not None:
            return namespace["result"]
        
        # Look for build123d shape types
        try:
            from build123d import Part, Solid, Compound, Sketch, Shape
            shape_types = (Part, Solid, Compound, Shape)
        except ImportError:
            return None
        
        # Find last defined shape variable
        candidates = []
        for key, val in namespace.items():
            if key.startswith("_") or key == "__builtins__":
                continue
            if isinstance(val, shape_types):
                candidates.append((key, val))
        
        if candidates:
            # Return the last one (most likely the final result)
            return candidates[-1][1]
        
        return None
    
    def get_model(self, name: str = None) -> Optional[ModelState]:
        """Get a model by name, or the active model."""
        name = name or self.active_model
        if name is None:
            return None
        return self.models.get(name)
    
    def export_model(self, name: str = None, format: str = "stl", 
                     path: Optional[Path] = None) -> Path:
        """Export model to file."""
        state = self.get_model(name)
        if state is None or state.shape is None:
            raise ValueError(f"No model '{name or self.active_model}' available")
        
        if path is None:
            path = self.workspace / f"{state.name}.{format}"
        
        from build123d import export_stl, export_step
        
        if format == "stl":
            export_stl(state.shape, str(path))
        elif format == "step":
            export_step(state.shape, str(path))
        elif format == "3mf":
            # build123d may support this
            try:
                from build123d import export_3mf
                export_3mf(state.shape, str(path))
            except ImportError:
                export_stl(state.shape, str(path.with_suffix('.stl')))
                path = path.with_suffix('.stl')
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return path
    
    def measure(self, name: str = None) -> dict:
        """Get measurements of the current model."""
        state = self.get_model(name)
        if state is None or state.shape is None:
            return {"error": "No model available"}
        
        shape = state.shape
        try:
            bb = shape.bounding_box()
            measurements = {
                "bounding_box": {
                    "min": [round(bb.min.X, 3), round(bb.min.Y, 3), round(bb.min.Z, 3)],
                    "max": [round(bb.max.X, 3), round(bb.max.Y, 3), round(bb.max.Z, 3)],
                    "width": round(bb.max.X - bb.min.X, 3),
                    "depth": round(bb.max.Y - bb.min.Y, 3),
                    "height": round(bb.max.Z - bb.min.Z, 3),
                },
                "volume_mm3": round(shape.volume, 3) if hasattr(shape, 'volume') else None,
                "surface_area_mm2": round(shape.area, 3) if hasattr(shape, 'area') else None,
                "center_of_mass": None,
            }
            
            try:
                com = shape.center()
                measurements["center_of_mass"] = [round(com.X, 3), round(com.Y, 3), round(com.Z, 3)]
            except Exception:
                pass
            
            # Face and edge counts
            try:
                measurements["face_count"] = len(shape.faces())
                measurements["edge_count"] = len(shape.edges())
                measurements["vertex_count"] = len(shape.vertices())
            except Exception:
                pass
            
            return measurements
        except Exception as e:
            return {"error": str(e)}
    
    def list_models(self) -> list[dict]:
        """List all loaded models with their info."""
        return [
            {**state.to_dict(), "active": name == self.active_model}
            for name, state in self.models.items()
        ]
