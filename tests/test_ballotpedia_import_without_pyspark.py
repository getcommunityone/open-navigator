"""The Ballotpedia module imports without pyspark (#307).

`save_to_bronze_layer` annotated its argument with `SparkSession`, which exists only when pyspark is installed. A
function's annotations are evaluated when its class body runs, so the import failed with NameError and the module's
JSON fallback never ran. pyspark is blocked in a subprocess, so the test holds whether or not pyspark is installed.
"""

from __future__ import annotations

import os
import subprocess
import sys

BLOCK_PYSPARK = "import sys; sys.modules.update(dict.fromkeys(['pyspark', 'pyspark.sql', 'pyspark.sql.types']))"


def _import_without_pyspark(module: str) -> subprocess.CompletedProcess:
    code = (
        f"{BLOCK_PYSPARK}; import importlib; m = importlib.import_module({module!r}); "
        "print('SPARK_AVAILABLE', getattr(m, 'SPARK_AVAILABLE', None))"
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)}
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, env=env)


def test_the_ballotpedia_module_imports_and_falls_back_without_pyspark():
    r = _import_without_pyspark("scrapers.ballotpedia.ballotpedia_integration")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "SPARK_AVAILABLE False" in r.stdout


def test_a_module_that_imports_it_loads_without_pyspark():
    r = _import_without_pyspark("scrapers.discovery.county_municipality_websites")
    assert r.returncode == 0, r.stderr[-2000:]
