"""Command-line entry point for the ShriTeq benchmark."""

from argparse import ArgumentParser
from pprint import pprint

from shriteq.config import SiteConfig
from shriteq.eval.benchmark import run_benchmark


def main() -> None:
    parser = ArgumentParser(description="Run the ShriTeq MPC/PPO benchmark")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--forecast-driven", action="store_true")
    args = parser.parse_args()
    pprint(run_benchmark(SiteConfig(), seed=args.seed, forecast_driven=args.forecast_driven))


if __name__ == "__main__":
    main()
