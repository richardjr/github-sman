"""CLI entry point for sman."""

import argparse

from sman import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sman",
        description="GitHub textual-based simple management CLI",
    )
    parser.add_argument(
        "--version", action="version", version=f"sman {__version__}"
    )
    parser.add_argument(
        "--org", help="Start with this org/account selected"
    )
    parser.parse_args()

    from sman.app import SmanApp

    app = SmanApp()
    app.run()
