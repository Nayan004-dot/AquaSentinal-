# Architecture
## Sensor path
Readings -> validation -> baseline comparison -> deviations and anomaly flags.

## Historical path
Source selection + location -> source-appropriate CGWB/CPCB records -> cleaning/matching -> per-parameter summaries and quality metadata.

## Future integration
Both outputs -> feature preprocessing -> documented risk scoring / Edge AI inference -> constrained RO recommendations.

Principles: preserve provenance, units and dates; missing is not zero; separate observed data, historical evidence, scores and recommendations; validate operating recommendations.
