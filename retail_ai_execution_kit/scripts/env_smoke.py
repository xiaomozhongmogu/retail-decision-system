"""环境冒烟检查（GOV-07）。

在项目虚拟环境中运行：
    .venv/bin/python scripts/env_smoke.py

只做最小验证：导入核心依赖、训练一个极小的 LightGBM 和逻辑回归、
以只读方式打开 DuckDB 并确认写入被拒绝、构造 Plotly 图对象。
不读取项目数据，不联网，不调用 LLM。全部通过时退出码为 0。
"""
from __future__ import annotations

import importlib
import json
import os
import platform
import sys
import tempfile

results: dict[str, object] = {}
failures: list[str] = []


def check(name, fn):
    try:
        results[name] = fn()
    except Exception as exc:  # 记录真实失败，不吞掉
        results[name] = f"FAIL: {type(exc).__name__}: {exc}"
        failures.append(name)


results["python"] = sys.version.split()[0]
results["executable"] = sys.executable
results["platform"] = platform.platform()
results["machine"] = platform.machine()

for mod in ["pandas", "pyarrow", "duckdb", "openpyxl", "sklearn", "lightgbm",
            "plotly", "streamlit", "openai", "pytest"]:
    check(f"import:{mod}", lambda m=mod: getattr(importlib.import_module(m), "__version__", "unknown"))


def lightgbm_fit():
    import numpy as np
    import lightgbm as lgb
    rng = np.random.default_rng(42)
    x = rng.normal(size=(200, 3))
    y = (x[:, 0] + rng.normal(scale=0.5, size=200) > 0).astype(int)
    model = lgb.LGBMClassifier(n_estimators=20, verbose=-1).fit(x, y)
    p = model.predict_proba(x)[:, 1]
    assert 0.0 <= p.min() and p.max() <= 1.0
    return {"n_train": 200, "proba_range": [round(float(p.min()), 3), round(float(p.max()), 3)]}


def sklearn_fit():
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    rng = np.random.default_rng(0)
    x = rng.normal(size=(100, 2))
    y = (x[:, 1] > 0).astype(int)
    return {"coef_shape": list(LogisticRegression().fit(x, y).coef_.shape)}


def duckdb_read_only():
    import duckdb
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "smoke.duckdb")
        con = duckdb.connect(path)
        con.execute("create table t as select range as i from range(5)")
        con.close()
        ro = duckdb.connect(path, read_only=True)
        n = ro.execute("select count(*) from t").fetchone()[0]
        try:
            ro.execute("insert into t values (99)")
            write_blocked = False
        except Exception:
            write_blocked = True
        ro.close()
    assert n == 5 and write_blocked, "只读连接应拒绝写入"
    return {"rows": n, "write_blocked_on_read_only": write_blocked}


def plotly_figure():
    import plotly.graph_objects as go
    fig = go.Figure(go.Bar(x=["a", "b"], y=[1, 2]))
    return {"traces": len(fig.data)}


check("lightgbm_fit", lightgbm_fit)
check("sklearn_logistic_fit", sklearn_fit)
check("duckdb_read_only", duckdb_read_only)
check("plotly_figure", plotly_figure)
results["failures"] = failures
print(json.dumps(results, ensure_ascii=False, indent=2))
sys.exit(1 if failures else 0)
