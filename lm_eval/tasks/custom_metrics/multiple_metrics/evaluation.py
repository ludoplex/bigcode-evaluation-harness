import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Optional

from .containerized_eval import eval_string_script

# Get working directory
WORKING_DIR = Path(__file__).parent.parent

# program: str => Result
CACHE = {}
CACHE_LOCK = Lock()


def cache_get(program: str) -> Optional[dict]:
    return CACHE[program] if program in CACHE else None


def cache_set(program: str, result: dict):
    if program in CACHE:
        print("Setting already-existing cache")
    CACHE[program] = result


def cached_eval_script(problem, index) -> dict:
    # here prompt is already included in completions
    program = problem["completions"][index] + "\n" + problem["tests"]
    CACHE_LOCK.acquire(True)
    cached = cache_get(program)
    if cached is not None:
        CACHE_LOCK.release()
        return cached
    else:
        result_yaml = {}
        cache_set(program, result_yaml)
        CACHE_LOCK.release()
        result_dict = eval_string_script(problem["language"], program)
        for k in result_dict.keys():
            result_yaml[k] = result_dict[k]
            result_yaml["timestamp"] = int(time.time())
        return result_yaml


def get_test_results_json_path(
    output_dir: str, problem_json_path: str, input_dir: Path
) -> Path:
    if input_dir:
        raise ValueError("input dir given")
    suffixes = ".results.json"
    return Path(output_dir) / (problem_json_path[: -len(".json")] + suffixes)


def evaluate_problem(
    output_dir: str, problem_json_path: str, max_workers: int, input_dir: Path = None
):
    with open(problem_json_path, "r") as f:
        problem = json.load(f)
    test_results_path = get_test_results_json_path(
        output_dir, problem_json_path, input_dir
    )
    test_results_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)

    test_results = problem.copy()
    del test_results["completions"]
    test_results["results"] = []

    num_problems = len(problem["completions"])
    min_problem = len(test_results["results"])

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for j in executor.map(
            lambda index: cached_eval_script(problem, index),
            range(min_problem, num_problems),
        ):
            test_results["results"].append(j)
            with open(test_results_path, "w") as f:
                f.write(json.dumps(test_results, indent=2))
