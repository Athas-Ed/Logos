from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .container import AppPorts
from .paths import default_gui_dist_dir


def create_app(
    ports: AppPorts,
    *,
    cors_allow_origins: Sequence[str] | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """Build FastAPI app: CORS, ``app.state.ports``, optional SPA static from ``src/gui/dist``."""
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
    except ImportError as e:
        raise ImportError(
            "logos.harness.ii_layer.create_app requires the 'fastapi' package."
        ) from e

    app = FastAPI(title="Logos I&I")
    app.state.ports = ports

    origins = list(cors_allow_origins) if cors_allow_origins is not None else ["*"]
    allow_credentials = "*" not in origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    root = static_dir if static_dir is not None else default_gui_dist_dir()
    if root.is_dir():
        app.mount("/", StaticFiles(directory=root, html=True), name="gui")

    return app
