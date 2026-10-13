"""Repository entry point for the installed-package synthetic retry walkthrough."""

from aau_harness.eval_retry_demo import create_demo as build_demo, demo_inputs as demo_inputs, main

__all__ = ["build_demo", "demo_inputs", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
