from pprint import pprint
from shriteq.config import SiteConfig
from shriteq.eval.benchmark import run_benchmark

results = run_benchmark(SiteConfig(), seed=42)
pprint(results)
