# ARMS review app location and approval boundary

> The ARMS review app runs on 127.0.0.1:8790 and parks feedback without applying skill changes.

_Saved: 2026-10-28T19:53:34Z_

Source: tools/arms/README.md. Start with python3 tools/arms/app.py, then open http://127.0.0.1:8790/. Feedback and recommendation carts persist locally in tools/arms/data. Parking feedback or copying a cart neither approves nor executes anything; an approved managed-skill change is applied and verified separately, then recorded with app.py resolve --user-approved.
