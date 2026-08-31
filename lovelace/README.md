How to use the Lovelace dashboard
=================================

This folder contains an example Lovelace dashboard (`dashboard.yaml`) you
can import into Home Assistant to display your IDM sensors.

Steps to use
1. Open Home Assistant UI.
2. Go to `Overview` (or any dashboard) and click the three-dot menu → Edit Dashboard → Raw configuration editor.
3. Paste the contents of `lovelace/dashboard.yaml` into the editor (merge into your existing `views` list or add as a new view).
4. Replace the example entity IDs (`sensor.idm_euro`, `sensor.idm_gewicht`, etc.) with the actual entities created by the IDM integration. You can find them in Developer Tools → States by filtering for `idm`.

Notes
- This is a simple example to get started. Feel free to customize card types and layout.
- If you use the `auto-entities` or other HACS cards, you can create more dynamic views that automatically pick up all `sensor.idm_*` entities.
