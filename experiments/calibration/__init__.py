"""Rubric-calibration harness (manual evaluation) — see experiments/README.md
"calibration" section. Not imported by bizstruct_ml or by any other part of
experiments/; kept entirely separate so it can never end up in the worker's
Docker image (see Dockerfile — it only COPYs src/, never experiments/).
"""
