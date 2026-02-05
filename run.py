#!/usr/bin/env python3
import argparse
import os
from app import create_app
from app.services.collector import run_collection_once


def main():
    parser = argparse.ArgumentParser(description="aimie-watchdog")
    sub = parser.add_subparsers(dest="cmd", required=True)

    web = sub.add_parser("web", help="Run web dashboard")
    web.add_argument("--host", default=os.getenv("WATCHDOG_HOST", "0.0.0.0"))
    web.add_argument("--port", type=int, default=int(os.getenv("WATCHDOG_PORT", "8080")))
    web.add_argument("--debug", action="store_true")

    collect = sub.add_parser("collect", help="Run one-shot collection")
    collect.add_argument("--no-diff", action="store_true", help="Skip diff generation")

    args = parser.parse_args()

    if args.cmd == "web":
        app = create_app()
        app.run(host=args.host, port=args.port, debug=args.debug)
        return

    if args.cmd == "collect":
        result = run_collection_once(make_diff=(not args.no_diff))
        # 종료코드 정책: CRIT 있으면 2, WARN만 있으면 1, 모두 OK면 0
        crit = result["summary"]["crit"]
        warn = result["summary"]["warn"]
        if crit > 0:
            raise SystemExit(2)
        if warn > 0:
            raise SystemExit(1)
        raise SystemExit(0)


if __name__ == "__main__":
    main()
