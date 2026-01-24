"""
CAD Agent MCP Server - Exposes build123d CAD tools via JSON-RPC/MCP protocol.

Tools:
- create_model: Execute build123d code to create a 3D model
- modify_model: Modify an existing model
- render_3d: Render 3D perspective/isometric view
- render_2d: Render 2D technical drawing with dimensions
- render_multiview: Render standard engineering multi-view drawing
- export_model: Export to STL/STEP/3MF
- measure_model: Get dimensions and geometry info
- list_models: List all loaded models
- analyze_printability: Check model for 3D printing issues
"""

import json
import sys
import base64
from pathlib import Path
from typing import Optional
import asyncio

# MCP protocol implementation (stdio JSON-RPC)
class MCPServer:
    """MCP Server implementing the Model Context Protocol over stdio."""
    
    def __init__(self):
        from src.cad_engine import CADEngine
        from src.renderer import Renderer, RenderConfig
        
        self.engine = CADEngine(workspace=Path("/workspace"))
        self.renderer = Renderer(
            config=RenderConfig(),
            output_dir=Path("/renders")
        )
        
        self.tools = {
            "create_model": self._create_model,
            "modify_model": self._modify_model,
            "render_3d": self._render_3d,
            "render_2d": self._render_2d,
            "render_multiview": self._render_multiview,
            "render_all": self._render_all,
            "export_model": self._export_model,
            "measure_model": self._measure_model,
            "list_models": self._list_models,
            "analyze_printability": self._analyze_printability,
            "get_render": self._get_render,
        }
    
    async def run(self):
        """Run the MCP server on stdio."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        
        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())
        
        # Send initialization
        init_response = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cad-agent", "version": "0.1.0"}
            }
        }
        
        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
                
                request = json.loads(line.decode().strip())
                response = await self._handle_request(request)
                
                if response:
                    writer.write((json.dumps(response) + "\n").encode())
                    await writer.drain()
                    
            except json.JSONDecodeError:
                continue
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": str(e)},
                    "id": None
                }
                writer.write((json.dumps(error_response) + "\n").encode())
                await writer.drain()
    
    async def _handle_request(self, request: dict) -> Optional[dict]:
        """Handle an incoming JSON-RPC request."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "cad-agent", "version": "0.1.0"}
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self._get_tool_definitions()}
            }
        
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            
            if tool_name in self.tools:
                try:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.tools[tool_name](**arguments)
                    )
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
                    }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                }
        
        return None
    
    def _get_tool_definitions(self) -> list[dict]:
        """Return MCP tool definitions."""
        return [
            {
                "name": "create_model",
                "description": "Create a 3D CAD model by executing build123d Python code. The code should use build123d API (from build123d import * is pre-loaded). Assign the final shape to a variable named 'result' or it will auto-detect the last Shape variable.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "build123d Python code to execute"},
                        "name": {"type": "string", "description": "Name for this model (default: 'default')"},
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "modify_model",
                "description": "Modify an existing model. The previous model is available as _models['name']. Write new code that uses or modifies it.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "build123d code to modify the model"},
                        "name": {"type": "string", "description": "Model name to modify"},
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "render_3d",
                "description": "Render a 3D view of the model. Returns the image path and base64 encoded PNG.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Model name (default: active model)"},
                        "view": {"type": "string", "enum": ["front", "back", "left", "right", "top", "bottom", "iso", "iso_back"], "description": "View angle"},
                    }
                }
            },
            {
                "name": "render_2d",
                "description": "Render a 2D technical drawing with visible/hidden lines and dimension annotations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Model name"},
                        "view": {"type": "string", "enum": ["front", "back", "left", "right", "top", "bottom"], "description": "Orthographic view"},
                        "with_dimensions": {"type": "boolean", "description": "Show dimension annotations (default: true)"},
                        "with_hidden": {"type": "boolean", "description": "Show hidden lines (default: true)"},
                    }
                }
            },
            {
                "name": "render_multiview",
                "description": "Render a standard engineering multi-view drawing (front, right, top + iso).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Model name"},
                        "views": {"type": "array", "items": {"type": "string"}, "description": "List of views to include"},
                    }
                }
            },
            {
                "name": "render_all",
                "description": "Render all standard views (3D iso, 2D front/right/top, multiview composite). Returns paths to all rendered images.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Model name"},
                    }
                }
            },
            {
                "name": "export_model",
                "description": "Export model to a file format suitable for 3D printing or CAD software.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Model name"},
                        "format": {"type": "string", "enum": ["stl", "step", "3mf"], "description": "Export format"},
                    }
                }
            },
            {
                "name": "measure_model",
                "description": "Get detailed measurements: bounding box, volume, surface area, face/edge/vertex counts, center of mass.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Model name"},
                    }
                }
            },
            {
                "name": "list_models",
                "description": "List all currently loaded models with their geometry info.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "analyze_printability",
                "description": "Analyze a model for 3D printing suitability: check wall thickness, overhangs, manifold status, etc.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Model name"},
                        "min_wall_thickness": {"type": "number", "description": "Minimum wall thickness in mm (default: 0.8)"},
                    }
                }
            },
            {
                "name": "get_render",
                "description": "Get a previously rendered image as base64 PNG. Use after render_* commands.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the render file"},
                    },
                    "required": ["path"]
                }
            },
        ]
    
    # --- Tool implementations ---
    
    def _create_model(self, code: str, name: str = "default") -> dict:
        result = self.engine.execute_code(code, name)
        if result["success"] and result["geometry"]:
            # Auto-render after creation
            model = self.engine.get_model(name)
            if model and model.shape:
                try:
                    render_path = self.renderer.render_3d(
                        model.shape, "iso", f"{name}_preview.png"
                    )
                    result["preview"] = str(render_path)
                    result["preview_base64"] = self._file_to_base64(render_path)
                except Exception as e:
                    result["render_error"] = str(e)
        return result
    
    def _modify_model(self, code: str, name: str = "default") -> dict:
        return self._create_model(code, name)
    
    def _render_3d(self, name: str = None, view: str = "iso") -> dict:
        model = self.engine.get_model(name)
        if not model or not model.shape:
            return {"error": f"No model '{name or 'active'}' found"}
        
        filename = f"{model.name}_3d_{view}.png"
        path = self.renderer.render_3d(model.shape, view, filename)
        return {
            "path": str(path),
            "view": view,
            "base64": self._file_to_base64(path)
        }
    
    def _render_2d(self, name: str = None, view: str = "front",
                   with_dimensions: bool = True, with_hidden: bool = True) -> dict:
        model = self.engine.get_model(name)
        if not model or not model.shape:
            return {"error": f"No model '{name or 'active'}' found"}
        
        filename = f"{model.name}_2d_{view}.png"
        path = self.renderer.render_2d(model.shape, view, with_dimensions, with_hidden, filename)
        return {
            "path": str(path),
            "view": view,
            "base64": self._file_to_base64(path)
        }
    
    def _render_multiview(self, name: str = None, views: list = None) -> dict:
        model = self.engine.get_model(name)
        if not model or not model.shape:
            return {"error": f"No model '{name or 'active'}' found"}
        
        filename = f"{model.name}_multiview.png"
        path = self.renderer.render_multiview(model.shape, views, filename=filename)
        return {
            "path": str(path),
            "base64": self._file_to_base64(path)
        }
    
    def _render_all(self, name: str = None) -> dict:
        model = self.engine.get_model(name)
        if not model or not model.shape:
            return {"error": f"No model '{name or 'active'}' found"}
        
        paths = self.renderer.render_all(model.shape, model.name)
        return {
            view: str(path) for view, path in paths.items()
        }
    
    def _export_model(self, name: str = None, format: str = "stl") -> dict:
        try:
            path = self.engine.export_model(name, format)
            return {"path": str(path), "format": format, "size_bytes": path.stat().st_size}
        except Exception as e:
            return {"error": str(e)}
    
    def _measure_model(self, name: str = None) -> dict:
        return self.engine.measure(name)
    
    def _list_models(self) -> dict:
        return {"models": self.engine.list_models()}
    
    def _analyze_printability(self, name: str = None, min_wall_thickness: float = 0.8) -> dict:
        model = self.engine.get_model(name)
        if not model or not model.shape:
            return {"error": f"No model '{name or 'active'}' found"}
        
        issues = []
        shape = model.shape
        
        try:
            # Check if manifold (watertight)
            from build123d import export_stl
            import trimesh
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
                tmp_path = f.name
            export_stl(shape, tmp_path)
            mesh = trimesh.load(tmp_path)
            Path(tmp_path).unlink()
            
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate(mesh.dump())
            
            analysis = {
                "is_watertight": mesh.is_watertight,
                "is_volume": mesh.is_volume,
                "euler_number": int(mesh.euler_number),
                "face_count": len(mesh.faces),
                "volume_mm3": round(float(mesh.volume), 2),
                "surface_area_mm2": round(float(mesh.area), 2),
            }
            
            if not mesh.is_watertight:
                issues.append("Model is not watertight (has holes). May cause printing issues.")
            
            if not mesh.is_volume:
                issues.append("Model does not form a valid volume.")
            
            # Check for very thin sections (approximate)
            bb = shape.bounding_box()
            dims = [
                abs(bb.max.X - bb.min.X),
                abs(bb.max.Y - bb.min.Y),
                abs(bb.max.Z - bb.min.Z)
            ]
            if any(d < min_wall_thickness for d in dims):
                issues.append(f"Bounding box has dimension < {min_wall_thickness}mm. May be too thin to print.")
            
            # Check for degenerate faces
            if hasattr(mesh, 'face_normals'):
                degenerate = np.sum(np.isnan(mesh.face_normals).any(axis=1))
                if degenerate > 0:
                    issues.append(f"{degenerate} degenerate faces detected.")
            
            analysis["issues"] = issues
            analysis["printable"] = len(issues) == 0
            analysis["min_wall_thickness_mm"] = min_wall_thickness
            
            return analysis
            
        except Exception as e:
            return {"error": f"Analysis failed: {e}", "issues": issues}
    
    def _get_render(self, path: str) -> dict:
        """Get a rendered image as base64."""
        p = Path(path)
        if not p.exists():
            return {"error": f"File not found: {path}"}
        return {
            "path": path,
            "base64": self._file_to_base64(p),
            "size_bytes": p.stat().st_size
        }
    
    @staticmethod
    def _file_to_base64(path: Path) -> str:
        """Read file and return base64 encoded string."""
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')


# --- HTTP API (alternative to MCP stdio) ---

def create_http_app():
    """Create a FastAPI app for HTTP-based access."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, JSONResponse
    from pydantic import BaseModel
    
    app = FastAPI(title="CAD Agent", version="0.1.0")
    server = MCPServer()
    
    class CreateModelRequest(BaseModel):
        code: str
        name: str = "default"
    
    class RenderRequest(BaseModel):
        name: str = None
        view: str = "iso"
        with_dimensions: bool = True
        with_hidden: bool = True
    
    class ExportRequest(BaseModel):
        name: str = None
        format: str = "stl"
    
    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}
    
    @app.post("/model/create")
    def create_model(req: CreateModelRequest):
        return server._create_model(req.code, req.name)
    
    @app.post("/model/modify")
    def modify_model(req: CreateModelRequest):
        return server._modify_model(req.code, req.name)
    
    @app.get("/model/list")
    def list_models():
        return server._list_models()
    
    @app.get("/model/{name}/measure")
    def measure(name: str = "default"):
        return server._measure_model(name)
    
    @app.post("/render/3d")
    def render_3d(req: RenderRequest):
        return server._render_3d(req.name, req.view)
    
    @app.post("/render/2d")
    def render_2d(req: RenderRequest):
        return server._render_2d(req.name, req.view, req.with_dimensions, req.with_hidden)
    
    @app.post("/render/multiview")
    def render_multiview(req: RenderRequest):
        return server._render_multiview(req.name)
    
    @app.post("/render/all")
    def render_all(req: RenderRequest):
        return server._render_all(req.name)
    
    @app.post("/export")
    def export_model(req: ExportRequest):
        result = server._export_model(req.name, req.format)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return FileResponse(result["path"], filename=Path(result["path"]).name)
    
    @app.post("/analyze/printability")
    def analyze(req: RenderRequest):
        return server._analyze_printability(req.name)
    
    @app.get("/renders/{filename}")
    def get_render_file(filename: str):
        path = Path("/renders") / filename
        if not path.exists():
            raise HTTPException(404, "Render not found")
        return FileResponse(path)
    
    return app


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CAD Agent Server")
    parser.add_argument("mode", choices=["mcp", "http"], default="http", nargs="?",
                       help="Server mode: 'mcp' for stdio MCP, 'http' for REST API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8123)
    
    args = parser.parse_args()
    
    if args.mode == "mcp":
        server = MCPServer()
        asyncio.run(server.run())
    else:
        import uvicorn
        app = create_http_app()
        uvicorn.run(app, host=args.host, port=args.port)
