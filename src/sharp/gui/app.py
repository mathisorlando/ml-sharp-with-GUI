"""FastAPI app for the SHARP Studio GUI."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import pickle
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sharp.cli.predict import DEFAULT_MODEL_URL, predict_image
from sharp.cli.render import render_gaussians
from sharp.models import PredictorParams, RGBGaussianPredictor, create_predictor
from sharp.utils import io
from sharp.utils.gaussians import SceneMetaData, save_ply

LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True)
class UploadPayload:
    filename: str
    content: bytes


class PredictorCache:
    """Cache predictor instances per checkpoint and device."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._models: dict[tuple[str, str], RGBGaussianPredictor] = {}
        self._unsafe: dict[tuple[str, str], bool] = {}

    def get(
        self, checkpoint_path: Path | None, device: str, allow_unsafe: bool
    ) -> tuple[RGBGaussianPredictor, bool]:
        key = (str(checkpoint_path) if checkpoint_path else "default", device)
        with self._lock:
            if key in self._models:
                used_unsafe = self._unsafe.get(key, False)
                if used_unsafe and not allow_unsafe:
                    raise ValueError(
                        "Checkpoint was loaded with unsafe deserialization. "
                        "Enable unsafe checkpoint loading to use it."
                    )
                return self._models[key], used_unsafe

            if checkpoint_path is None:
                LOGGER.info("Downloading default model from %s", DEFAULT_MODEL_URL)
                state_dict = torch.hub.load_state_dict_from_url(DEFAULT_MODEL_URL, progress=True)
                used_unsafe = False
            else:
                LOGGER.info("Loading checkpoint from %s", checkpoint_path)
                used_unsafe = False
                try:
                    state_dict = torch.load(checkpoint_path, weights_only=True)
                except (pickle.UnpicklingError, RuntimeError) as exc:
                    if not allow_unsafe:
                        raise ValueError(
                            "Checkpoint could not be loaded with safe deserialization. "
                            "Enable unsafe checkpoint loading for trusted files."
                        ) from exc
                    LOGGER.warning(
                        "Loading checkpoint with unsafe deserialization. "
                        "Only enable this for trusted files."
                    )
                    state_dict = torch.load(checkpoint_path, weights_only=False)
                    used_unsafe = True

            predictor = create_predictor(PredictorParams())
            predictor.load_state_dict(state_dict)
            predictor.eval()
            predictor.to(device)
            self._models[key] = predictor
            self._unsafe[key] = used_unsafe
            return predictor, used_unsafe


PREDICTOR_CACHE = PredictorCache()
INFERENCE_LOCK = threading.Lock()


class OutputState:
    """Track the active output root and per-run output folders."""

    def __init__(self, root: Path) -> None:
        self._lock = threading.Lock()
        self._root = root
        self._runs: dict[str, Path] = {}

    def get_root(self) -> Path:
        with self._lock:
            return self._root

    def set_root(self, root: Path) -> None:
        with self._lock:
            self._root = root

    def set_run_root(self, run_id: str, root: Path) -> None:
        with self._lock:
            self._runs[run_id] = root

    def get_run_root(self, run_id: str) -> Path:
        with self._lock:
            return self._runs.get(run_id, self._root)


def config_path() -> Path:
    if sys.platform.startswith("darwin"):
        base_dir = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base_dir / "SHARP Studio" / "config.json"


def read_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        LOGGER.warning("Failed to read config file at %s", path)
        return {}


def write_config(payload: dict[str, Any]) -> None:
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
    except OSError:
        LOGGER.warning("Failed to write config file at %s", path)


def default_output_root() -> Path:
    home_dir = Path.home()
    documents = home_dir / "Documents"
    base_dir = documents if documents.exists() else home_dir
    return base_dir / "SHARP Studio" / "Outputs"


def normalize_output_root(output_root: Path) -> Path:
    resolved = output_root.expanduser().resolve(strict=False)
    if resolved.exists() and not resolved.is_dir():
        raise ValueError("Output path must be a folder.")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def load_output_root(cli_output_root: Path | None) -> Path:
    if cli_output_root is not None:
        normalized = normalize_output_root(cli_output_root)
        write_config({"output_root": str(normalized)})
        return normalized

    config = read_config()
    configured = config.get("output_root")
    if configured:
        try:
            return normalize_output_root(Path(configured))
        except ValueError:
            LOGGER.warning("Configured output root is invalid, using default.")

    return normalize_output_root(default_output_root())


def select_output_folder(initial_dir: Path) -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("Folder picker is unavailable on this system.") from exc

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    selected = filedialog.askdirectory(
        initialdir=str(initial_dir),
        title="Select output folder",
        mustexist=False,
    )
    root.destroy()
    if not selected:
        return None
    return Path(selected)


def open_output_folder(folder: Path) -> None:
    if sys.platform.startswith("darwin"):
        subprocess.run(["open", str(folder)], check=True)
    elif os.name == "nt":
        subprocess.run(["explorer", str(folder)], check=True)
    else:
        subprocess.run(["xdg-open", str(folder)], check=True)


def resolve_device(requested: str) -> str:
    """Resolve the device string to a concrete device."""
    if requested == "default":
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch, "mps") and torch.mps.is_available():
            return "mps"
        return "cpu"

    if requested not in {"cpu", "cuda", "mps"}:
        raise ValueError("Device must be one of: cpu, cuda, mps, default")
    if requested == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA is not available on this machine.")
    if requested == "mps" and not (hasattr(torch, "mps") and torch.mps.is_available()):
        raise ValueError("MPS is not available on this machine.")
    return requested


def safe_filename(name: str) -> str:
    """Sanitize filename to avoid path traversal and invalid characters."""
    base = Path(name).name.replace(" ", "_")
    filtered = "".join(ch for ch in base if ch.isalnum() or ch in {".", "_", "-"})
    return filtered or "upload"


def unique_filename(name: str, used: set[str]) -> str:
    """Ensure unique filenames within a run directory."""
    base = Path(name).stem
    suffix = Path(name).suffix
    candidate = f"{base}{suffix}"
    counter = 1
    while candidate in used:
        candidate = f"{base}-{counter}{suffix}"
        counter += 1
    used.add(candidate)
    return candidate


def ensure_within(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if not resolved_candidate.is_relative_to(resolved_root):
        raise HTTPException(status_code=400, detail="Invalid path.")
    return resolved_candidate


def store_checkpoint(payload: UploadPayload, output_root: Path) -> Path:
    digest = hashlib.sha256(payload.content).hexdigest()
    cache_dir = output_root / "_checkpoints"
    cache_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = cache_dir / f"{digest}.pt"
    if not checkpoint_path.exists():
        checkpoint_path.write_bytes(payload.content)
    return checkpoint_path


def create_bundle_zip(run_dir: Path, bundle_path: Path) -> None:
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_handle:
        for path in run_dir.rglob("*"):
            if path == bundle_path:
                continue
            if path.is_dir():
                continue
            zip_handle.write(path, path.relative_to(run_dir))


def write_preview(image_np: Any, output_path: Path, max_size: int = 720) -> None:
    from PIL import Image

    image = Image.fromarray(image_np)
    image.thumbnail((max_size, max_size))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="JPEG", quality=92, optimize=True)


def process_inference(
    uploads: list[UploadPayload],
    checkpoint: UploadPayload | None,
    requested_device: str,
    render: bool,
    allow_unsafe: bool,
    output_root: Path,
) -> dict[str, Any]:
    if not uploads:
        raise HTTPException(status_code=400, detail="No images provided.")

    try:
        device = resolve_device(requested_device)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    render_enabled = render and device == "cuda" and torch.cuda.is_available()
    warnings: list[str] = []
    if render and not render_enabled:
        warnings.append("Rendering requires CUDA. Video render was skipped.")

    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = None
    if checkpoint is not None:
        checkpoint_path = store_checkpoint(checkpoint, output_root)

    try:
        predictor, used_unsafe = PREDICTOR_CACHE.get(checkpoint_path, device, allow_unsafe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if used_unsafe:
        warnings.append(
            "Checkpoint loaded with unsafe deserialization. Only use trusted checkpoint files."
        )

    outputs: list[dict[str, Any]] = []
    used_names: set[str] = set()

    for index, upload in enumerate(uploads, start=1):
        safe_name = unique_filename(safe_filename(upload.filename), used_names)
        input_path = run_dir / f"{index:02d}_{safe_name}"
        input_path.write_bytes(upload.content)

        image, _, f_px = io.load_rgb(input_path)
        height, width = image.shape[:2]
        gaussians = predict_image(predictor, image, f_px, torch.device(device))

        stem = Path(safe_name).stem
        ply_path = run_dir / f"{stem}.ply"
        save_ply(gaussians, f_px, (height, width), ply_path)

        preview_path = run_dir / f"{stem}.preview.jpg"
        write_preview(image, preview_path)

        output: dict[str, Any] = {
            "name": safe_name,
            "ply": ply_path.name,
            "preview": preview_path.name,
        }

        if render_enabled:
            video_path = run_dir / f"{stem}.mp4"
            metadata = SceneMetaData(f_px, (width, height), "linearRGB")
            render_gaussians(gaussians, metadata, video_path)

            output["video"] = video_path.name
            depth_path = video_path.with_suffix(".depth.mp4")
            if depth_path.exists():
                output["depth_video"] = depth_path.name

        outputs.append(output)

    manifest = {
        "run_id": run_id,
        "device": device,
        "render_requested": render,
        "render_enabled": render_enabled,
        "outputs": outputs,
        "warnings": warnings,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    bundle_path = run_dir / "bundle.zip"
    create_bundle_zip(run_dir, bundle_path)

    return {
        "run_id": run_id,
        "device": device,
        "render_requested": render,
        "render_enabled": render_enabled,
        "outputs": outputs,
        "warnings": warnings,
        "bundle": bundle_path.name,
    }


def create_app(output_root: Path | None = None) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="SHARP Studio", docs_url=None, redoc_url=None)

    base_dir = Path(__file__).resolve().parent
    static_dir = base_dir / "static"
    templates_dir = base_dir / "templates"

    output_root = load_output_root(output_root)
    output_state = OutputState(output_root)

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=str(templates_dir))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("index.html", {"request": request})

    @app.post("/api/predict")
    async def predict(
        images: list[UploadFile] = File(...),
        checkpoint: UploadFile | None = File(None),
        device: str = Form("default"),
        render: bool = Form(False),
        unsafe_checkpoint: bool = Form(False),
    ) -> JSONResponse:
        uploads = [
            UploadPayload(filename=image.filename, content=await image.read())
            for image in images
        ]
        checkpoint_payload = None
        if checkpoint is not None and checkpoint.filename:
            checkpoint_payload = UploadPayload(
                filename=checkpoint.filename, content=await checkpoint.read()
            )

        def run() -> dict[str, Any]:
            with INFERENCE_LOCK:
                current_root = output_state.get_root()
                result = process_inference(
                    uploads=uploads,
                    checkpoint=checkpoint_payload,
                    requested_device=device,
                    render=render,
                    allow_unsafe=unsafe_checkpoint,
                    output_root=current_root,
                )
                output_state.set_run_root(result["run_id"], current_root)
                return result

        result = await asyncio.to_thread(run)

        for output in result["outputs"]:
            output["ply"] = f"/api/file/{result['run_id']}/{output['ply']}"
            output["preview"] = f"/api/file/{result['run_id']}/{output['preview']}"
            if "video" in output:
                output["video"] = f"/api/file/{result['run_id']}/{output['video']}"
            if "depth_video" in output:
                output["depth_video"] = f"/api/file/{result['run_id']}/{output['depth_video']}"

        result["bundle"] = f"/api/file/{result['run_id']}/{result['bundle']}"
        return JSONResponse(result)

    @app.get("/api/file/{run_id}/{filename}")
    async def download_file(run_id: str, filename: str) -> FileResponse:
        run_root = output_state.get_run_root(run_id)
        run_dir = ensure_within(run_root, run_root / run_id)
        file_path = ensure_within(run_dir, run_dir / filename)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found.")
        return FileResponse(file_path)

    @app.get("/api/output-root")
    async def get_output_root() -> JSONResponse:
        return JSONResponse({"path": str(output_state.get_root())})

    @app.post("/api/output-root/select")
    async def select_output_root() -> JSONResponse:
        try:
            selected = select_output_folder(output_state.get_root())
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if selected is None:
            return JSONResponse({"path": str(output_state.get_root()), "changed": False})
        try:
            normalized = normalize_output_root(selected)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        output_state.set_root(normalized)
        write_config({"output_root": str(normalized)})
        return JSONResponse({"path": str(normalized), "changed": True})

    @app.post("/api/output-root/open")
    async def open_output_root() -> JSONResponse:
        try:
            open_output_folder(output_state.get_root())
        except (OSError, subprocess.CalledProcessError) as exc:
            raise HTTPException(status_code=500, detail="Failed to open output folder.") from exc
        return JSONResponse({"path": str(output_state.get_root())})

    return app


def run(host: str = "127.0.0.1", port: int = 7860, output_root: Path | None = None) -> None:
    """Run the GUI using uvicorn."""
    import uvicorn

    app = create_app(output_root=output_root)
    uvicorn.run(app, host=host, port=port)
