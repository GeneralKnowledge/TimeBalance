"""M2 forecasting research laboratory: walk-forward experiments over stored history.

Layers (each its own module):

- ``config``    typed, hashable experiment configuration (what to run)
- ``data``      replay-mode-dispatched history access, forecast origins, inputs and realised targets
- ``store``     the research results database (separate from the market-data database)
- ``runner``    sequential model execution over prepared origins, resumable
- ``metrics``   point, quantile and probabilistic scores (pure functions)
- ``analysis``  scoring, aggregation, paired comparisons and calibration
- ``report``    Markdown/CSV/JSON/SVG outputs under ``reports/experiments/<id>/``

This is a research system. It produces forecasts and scores; it never produces trading signals.
"""
