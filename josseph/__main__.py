import argparse
import logging
import sys

from josseph.utils import CONFIGS_DIR
from josseph.pipeline.app import RepositoryAnalysisPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run repository analysis using a YAML configuration file."
    )
    parser.add_argument(
        "config_path",
        nargs="?",
        default=str(CONFIGS_DIR / "config.yaml"),
        help="Path to the YAML configuration file (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Ignore cached results and re-run all extractors.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("""
       _  ____   _____ _____            _     
      | |/ __ \\ / ____/ ____|          | |    
      | | |  | | (___| (___   ___ _ __ | |__  
  _   | | |  | |\\___ \\\\___ \\ / _ \\ '_ \\| '_ \\ 
 | |__| | |__| |____) |___) |  __/ |_) | | | |
  \\____/ \\____/|_____/_____/ \\___| .__/|_| |_|
                                 | |          
                                 |_|          
""")
    try:
        return RepositoryAnalysisPipeline().run(args)
    except (FileNotFoundError, ValueError) as exc:
        logger = logging.getLogger("josseph.__main__")
        if logger.hasHandlers():
            logger.exception("Startup failed: %s", exc)
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
