#!/bin/zsh
# PLAN.md order: gate arms, gate check (stops on failure), then the four ICC arms.
set -e
cd "$(dirname "$0")"
PY=../trident-plism/.venv/bin/python
for arm in gate_otsu gate_grandqc; do $PY scripts/02_segment_icc.py $arm > logs/$arm.txt 2>&1; echo "$arm exit $?"; done
$PY scripts/gate_check.py
for arm in icc_otsu icc_grandqc icc_hest icc_hest_artifacts; do $PY scripts/02_segment_icc.py $arm > logs/$arm.txt 2>&1; echo "$arm exit $?"; done
$PY scripts/03_score_icc.py > logs/score.txt 2>&1; echo "score exit $?"
