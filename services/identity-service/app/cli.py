"""Command-line utilities. Usage: python -m app.cli seed-demo-users"""

import argparse
import sys
from collections.abc import Sequence

from app.core.config import ConfigurationError, Environment, Settings, load_settings
from app.db.session import build_engine, build_session_factory
from app.services.seed_service import seed_demo_users


def run_seed(settings: Settings) -> int:
    if settings.app_env == Environment.PRODUCTION:
        print("Refusing to seed demo accounts when APP_ENV=production.", file=sys.stderr)
        return 2
    if settings.seed_demo_password is None:
        print("SEED_DEMO_PASSWORD must be set to seed demo accounts.", file=sys.stderr)
        return 2
    engine = build_engine(settings.database_url)
    try:
        with build_session_factory(engine)() as session:
            results = seed_demo_users(session, settings.seed_demo_password.get_secret_value())
    except ValueError as exc:
        print(f"Seeding failed: {exc}", file=sys.stderr)
        return 2
    finally:
        engine.dispose()
    for result in results:
        status = "created" if result.created else "exists (unchanged)"
        print(f"{result.role.value:<13} {result.email:<40} {status}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Identity service utilities")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("seed-demo-users", help="Create fictional demo accounts (development only)")
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.command == "seed-demo-users":
        return run_seed(settings)
    return 1  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
