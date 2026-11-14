#!/bin/zsh
# REL-02 second clean clone: only commands written in docs/runbook.md (sections 1-4a, 7), in order.
set -u
R=$1; cd $R
step(){ echo "\n### $1"; date -u +%FT%TZ; }
step "clone"; git clone -q https://github.com/xiaomozhongmogu/retail-decision-system.git repo; cd repo; git log --oneline -1; cd retail_ai_execution_kit
step "1 install"; uv venv -q --python 3.12 .venv && uv pip sync -q --python .venv/bin/python requirements.lock; echo "exit=$?"; .venv/bin/python scripts/env_smoke.py > /dev/null; echo "env_smoke exit=$?"
step "2 snapshot for ledger validation"; mkdir -p data/raw/data02-input-snapshot && cp -R ../ecommerce-sample-database-100k/01_source ../ecommerce-sample-database-100k/02_historical_utf8 data/raw/data02-input-snapshot/; echo "exit=$?"
step "3 ETL"; .venv/bin/python src/retail_bi/pipeline.py build | tail -1; echo "build exit=$pipestatus[1]"
.venv/bin/python src/retail_bi/warehouse/release.py publish > /dev/null; echo "publish exit=$?"
.venv/bin/python src/retail_bi/warehouse/release.py status | grep '"version"'
step "3 data-layer chain (docs/data_readme.md section 2)"; CMD=$(awk '/## 2. 一键重建/,/## 3/' docs/data_readme.md | sed -n '/```bash/,/```/p' | grep -v '```'); eval "$CMD" | tail -1; echo "chain exit=$?"
step "4a samples and features"; .venv/bin/python src/retail_bi/features/build_samples.py > /dev/null; echo "samples exit=$?"; .venv/bin/python src/retail_bi/features/customer_features.py > /dev/null; echo "features exit=$?"
step "git status after rebuild"; git status --short
step "7 regression"; .venv/bin/python tests/release/run_regression.py --skip-live --allow-dirty; echo "regression exit=$?"
step "ledger"; python3 scripts/project.py validate | head -12
step "done"
