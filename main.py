from __future__ import annotations

import argparse
from pathlib import Path

from app.ui import serve_app


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    default_output = (base_dir / "output").resolve()

    parser = argparse.ArgumentParser(description="PDF 解析 + DeepSeek 文献要点分析（本地 Web 界面）")
    parser.add_argument("--output", default=str(default_output), help="结果输出目录（默认 ./output）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    serve_app(Path(args.output).resolve(), host=args.host, port=args.port)

 
if __name__ == "__main__":
    main()

 