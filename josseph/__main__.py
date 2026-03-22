import argparse
import os

from josseph.utils import ROOT
from josseph.run_analysis import RepositoryAnalysisPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repos",
        dest="repos_file",
        default=str(ROOT / "repos.txt"),
        help="Path to the file containing repository URLs (default: %(default)s)",
    )
    parser.add_argument(
        "--clone-depth",
        default=None,
        help="Depth to use when cloning repositories)",
    )
    parser.add_argument(
        "--tool",
        action="append",
        dest="tools",
        help="Metric tool name to run (can be provided multiple times; default: all)",
    )
    parser.add_argument(
        "--github-token",
        default=None,
        help="GitHub token to use for API requests (default: env GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 1,
        help="Maximum number of repositories to analyse in parallel (default: CPU count)",
    )
    return parser.parse_args()


def main() -> None:
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
    args = parse_args()
    RepositoryAnalysisPipeline().run(args)

if __name__ == "__main__":
    main()
