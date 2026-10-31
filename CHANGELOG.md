# Documentation Update Notes

This update reflects the agreed AquaSentinel V1 architecture:

- Historical context remains source/location-selectable using CGWB groundwater and CPCB surface-water records.
- Live ESP32 monitoring is at the treated-water outlet and uses TDS, pH, turbidity and water temperature.
- ESP32 telemetry is sent over HTTPS to FastAPI hosted on Person 1's Ubuntu laptop; a secure tunnel is planned for cross-network access.
- Backend stores raw sensor data and creates completed 30-minute summaries.
- Dashboard V1 has two functional sections: Historical Source Intelligence and Outlet Water Monitoring.
- Filter Performance & Maintenance Monitoring and RO Decision Engine are R&D placeholders in V1.
- Team roles are documented for Persons 1, 2 and 3.
