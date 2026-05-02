from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class HardwareSpec:
    summary: str
    target_mcu: str
    pins: Dict[str, str]
    rtos_tasks: List[str]
    memory_kb: int
    interfaces: List[str]
    assumptions: List[str]


def mock_llm_call(user_request: str) -> Dict[str, object]:
    normalized = user_request.lower()
    if "stm32" in normalized:
        target_mcu = "STM32"
        pins = {"SCL": "PB8", "SDA": "PB9", "RESET": "PA0"}
    else:
        target_mcu = "ESP32"
        pins = {"SCL": "GPIO22", "SDA": "GPIO21", "RESET": "GPIO16"}

    interfaces = []
    if "i2c" in normalized:
        interfaces.append("I2C")
    if "spi" in normalized:
        interfaces.append("SPI")
    if not interfaces:
        interfaces.append("GPIO")

    rtos_tasks = ["telemetry_task"]
    if "display" in normalized or "oled" in normalized:
        rtos_tasks.insert(0, "display_update_task")
    if "i2c" in normalized:
        rtos_tasks.append("i2c_service_task")

    memory_kb = 96 if target_mcu == "ESP32" else 48
    summary = f"Generated {target_mcu} spec for request: {user_request.strip()}"

    assumptions = [
        "RTOS scheduler is initialized before user tasks run.",
        "I2C bus speed defaults to 400kHz unless specified.",
        "Display buffer updates are periodic and non-blocking.",
    ]

    return {
        "summary": summary,
        "target_mcu": target_mcu,
        "pins": pins,
        "rtos_tasks": rtos_tasks,
        "memory_kb": memory_kb,
        "interfaces": interfaces,
        "assumptions": assumptions,
    }


def mock_zhipu_call(user_request: str) -> Dict[str, object]:
    return mock_llm_call(user_request)


def plan_hardware(user_request: str) -> HardwareSpec:
    spec_payload = mock_llm_call(user_request)
    return HardwareSpec(**spec_payload)
