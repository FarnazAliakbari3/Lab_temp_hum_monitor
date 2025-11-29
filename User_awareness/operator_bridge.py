"""Bridge between user interfaces (Telegram, CLI, etc.) and the REST registry."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class OperatorBridge:
    def __init__(self, base_url: str = "http://localhost:8080", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ HTTP helpers
    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {}
        if payload is not None:
            encoded = json.dumps(payload).encode("utf-8")
            data = encoded
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8") or "{}"
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
                return json.loads(body)
            except Exception:
                logger.error("HTTP error %s for %s %s: %s", exc.code, method, url, exc.reason)
                return {"error": exc.reason}
        except urllib.error.URLError as exc:
            logger.error("HTTP request failed for %s %s: %s", method, url, exc.reason)
            return {"error": str(exc.reason)}

    def _get(self, path: str) -> Dict[str, Any]:
        return self._request("GET", path)

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", path, payload)

    def _put(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", path, payload)

    def _delete(self, path: str) -> Dict[str, Any]:
        return self._request("DELETE", path)

    # ------------------------------------------------------------------ exposed ops
    def status(self) -> Dict[str, Any]:
        return self._get("/status")

    def send_command(self, lab_id: str, actuator_id: str, action: str, source: str = "bot") -> Dict[str, Any]:
        return self._post("/command", {"lab_id": lab_id, "actuator_id": actuator_id, "action": action, "source": source})

    def list_labs(self) -> Dict[str, Any]:
        return self._get("/labs")

    def add_lab(self, lab_id: str, name: str, notes: str = "") -> Dict[str, Any]:
        return self._post("/labs", {"lab_id": lab_id, "name": name, "notes": notes})

    def update_lab(self, lab_id: str, **fields) -> Dict[str, Any]:
        return self._put(f"/lab/{urllib.parse.quote(lab_id)}", fields)

    def remove_lab(self, lab_id: str) -> Dict[str, Any]:
        return self._delete(f"/lab/{urllib.parse.quote(lab_id)}")

    def list_sensors(self, lab_id: Optional[str] = None) -> Dict[str, Any]:
        if lab_id:
            return self._get(f"/sensors?lab_id={urllib.parse.quote(lab_id)}")
        return self._get("/sensors")

    def add_sensor(self, lab_id: str, sensor_id: str, sensor_type: str) -> Dict[str, Any]:
        return self._post("/sensors", {"lab_id": lab_id, "sensor_id": sensor_id, "type": sensor_type})

    def update_sensor(self, sensor_id: str, **fields) -> Dict[str, Any]:
        return self._put(f"/sensor/{urllib.parse.quote(sensor_id)}", fields)

    def remove_sensor(self, sensor_id: str) -> Dict[str, Any]:
        return self._delete(f"/sensor/{urllib.parse.quote(sensor_id)}")

    def list_actuators(self, lab_id: Optional[str] = None) -> Dict[str, Any]:
        if lab_id:
            return self._get(f"/actuators?lab_id={urllib.parse.quote(lab_id)}")
        return self._get("/actuators")

    def add_actuator(self, lab_id: str, actuator_id: str, actuator_type: str) -> Dict[str, Any]:
        return self._post("/actuators", {"lab_id": lab_id, "actuator_id": actuator_id, "type": actuator_type})

    def update_actuator(self, actuator_id: str, **fields) -> Dict[str, Any]:
        return self._put(f"/actuator/{urllib.parse.quote(actuator_id)}", fields)

    def remove_actuator(self, actuator_id: str) -> Dict[str, Any]:
        return self._delete(f"/actuator/{urllib.parse.quote(actuator_id)}")

    def update_threshold(self, lab_id: str, **values) -> Dict[str, Any]:
        return self._put(f"/threshold/{urllib.parse.quote(lab_id)}", values)

    def get_permissions(self) -> Dict[str, Any]:
        return self._get("/permissions")
