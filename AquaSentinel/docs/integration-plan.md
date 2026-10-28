# Integration Plan
Before integration:
- Sensor module returns readings, deviations, anomaly flags and status.
- Historical module returns source/location match, per-parameter summaries, sample counts, latest dates and quality warnings.
- Both modules have a README, tests and example output.

Checklist:
- [ ] Agree field names and units
- [ ] Confirm measurement point and source type
- [ ] Define missing-value policy
- [ ] Define score meaning and direction
- [ ] Define target labels if training a supervised model
- [ ] Evaluate on appropriate held-out data
- [ ] Map scores to recommendations only with validated operating rules
