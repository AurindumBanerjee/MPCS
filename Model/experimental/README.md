# Model/experimental

Active development trunk. New mechanisms are built here first.

- `MCPS_Z.py` — Z-number variant (feature values carry a `(value, confidence)`
  pair), backed by a d-left counting Bloom filter that supports deletion.
  Includes the expert-in-the-loop teaching flow (Teach Expert button):
  the expert supplies the correct action, it is stored as a high-confidence
  flagged experience and weighted more heavily in scoring, while the model's
  original (wrong) choice is demoted.

Run:

    python MCPS_Z.py
