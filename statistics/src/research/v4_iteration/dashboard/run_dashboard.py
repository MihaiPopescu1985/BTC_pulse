from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse
import webbrowser

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.path_config import DEFAULT_PRICE_JSON_PATH
from src.research.v4_iteration.dashboard.dashboard_utils import build_runtime_registry, load_view_payload


STATIC_DIR = Path(__file__).resolve().parent / "static"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the reusable SAFE research dashboard.")
    parser.add_argument("--dataset", help="Optional custom dataset CSV path.")
    parser.add_argument("--view", help="Optional registered view name.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--price-json", default=str(DEFAULT_PRICE_JSON_PATH))
    parser.add_argument("--open-browser", action="store_true", help="Open the dashboard in the default browser.")
    parser.add_argument("--check", action="store_true", help="Validate registered views and exit without starting the server.")
    return parser.parse_args()


class DashboardHandler(SimpleHTTPRequestHandler):
    server_version = "SafeResearchDashboard/1.0"

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    @property
    def dashboard_state(self) -> "DashboardState":
        return self.server.dashboard_state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/api/config", "/api/data"}:
            self._handle_api(parsed)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def _handle_api(self, parsed: Any) -> None:
        try:
            if parsed.path == "/api/config":
                payload = self.dashboard_state.config_payload()
            elif parsed.path == "/api/data":
                query = parse_qs(parsed.query)
                view_name = query.get("view", [self.dashboard_state.active_view])[0]
                payload = self.dashboard_state.data_payload(view_name)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            body = json.dumps(payload, allow_nan=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:  # pragma: no cover
            body = json.dumps({"error": str(exc)}, allow_nan=False).encode("utf-8")
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


class DashboardState:
    def __init__(self, *, registry: dict[str, dict[str, Any]], active_view: str, price_json_path: str | Path) -> None:
        self.registry = registry
        self.active_view = active_view
        self.price_json_path = price_json_path

    def config_payload(self) -> dict[str, Any]:
        return {
            "active_view": self.active_view,
            "views": [
                {
                    "name": name,
                    "label": definition.get("label", name),
                    "description": definition.get("description", ""),
                    "path": definition.get("path", ""),
                }
                for name, definition in self.registry.items()
            ],
        }

    def data_payload(self, view_name: str) -> dict[str, Any]:
        return load_view_payload(self.registry, view_name, price_json_path=self.price_json_path)


def validate_views(state: DashboardState, view_names: list[str]) -> None:
    for view_name in view_names:
        state.data_payload(view_name)


def main() -> None:
    args = parse_args()
    registry, active_view = build_runtime_registry(args.dataset)
    if args.view:
        if args.view not in registry:
            raise KeyError(f"Unknown dashboard view: {args.view}")
        active_view = args.view

    state = DashboardState(registry=registry, active_view=active_view, price_json_path=args.price_json)
    if args.check:
        view_names = sorted(registry.keys())
        validate_views(state, view_names)
        print("Dashboard views validated:")
        for view_name in view_names:
            print(f"- {view_name}")
        return

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    server.dashboard_state = state  # type: ignore[attr-defined]
    url = f"http://{args.host}:{args.port}/"
    print(f"SAFE research dashboard running at {url}")
    print(f"Active view: {active_view}")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
