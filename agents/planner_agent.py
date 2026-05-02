"""
planner_agent.py
================
Role: Planner Agent
Responsibility:
    Accepts a free-form natural-language task description from the user and
    converts it into a structured hardware specification dictionary that the
    Coder Agent can consume directly.

LLM backend
-----------
Real deployments should replace ``mock_zhipu_call`` with an authenticated
call to the ZhipuAI GLM-4 (or equivalent) API.  The mock intentionally
mirrors the JSON contract a real model would return so that swapping the
backend is a one-line change.

Output contract (``HardwareSpec``)
-----------------------------------
{
    "mcu":          str,          # Target microcontroller, e.g. "ESP32"
    "rtos":         str,          # RTOS in use,            e.g. "FreeRTOS"
    "peripherals":  list[dict],   # [{"name": str, "interface": str, "pins": dict}]
    "tasks":        list[dict],   # [{"name": str, "priority": int, "stack_size": int,
                                  #   "period_ms": int, "description": str}]
    "memory": {
        "heap_kb":  int,
        "stack_kb": int,
        "notes":    str
    },
    "constraints":  list[str]     # Additional safety / timing constraints
}
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
HardwareSpec = Dict[str, Any]


# ---------------------------------------------------------------------------
# Mock LLM back-end
# ---------------------------------------------------------------------------

def mock_zhipu_call(system_prompt: str, user_message: str) -> str:
    """
    Simulate a ZhipuAI GLM-4 API call.

    In production replace the body of this function with:

        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=os.environ["ZHIPU_API_KEY"])
        response = client.chat.completions.create(
            model="glm-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
        )
        return response.choices[0].message.content

    The mock analyses keywords in the user message and returns a realistic
    JSON spec so the rest of the pipeline can execute end-to-end without a
    live API key.
    """
    msg_lower = user_message.lower()

    # ------------------------------------------------------------------ I2C
    if "i2c" in msg_lower and "oled" in msg_lower:
        spec: HardwareSpec = {
            "mcu": "ESP32",
            "rtos": "FreeRTOS",
            "peripherals": [
                {
                    "name": "SSD1306_OLED",
                    "interface": "I2C",
                    "pins": {"SDA": "GPIO21", "SCL": "GPIO22"},
                    "address": "0x3C",
                    "resolution": "128x64",
                }
            ],
            "tasks": [
                {
                    "name": "oled_display_task",
                    "priority": 5,
                    "stack_size": 4096,
                    "period_ms": 100,
                    "description": "Initialise SSD1306 over I2C and refresh the display buffer every 100 ms.",
                }
            ],
            "memory": {
                "heap_kb": 32,
                "stack_kb": 4,
                "notes": "Display frame-buffer allocated on heap; guard with pvPortMalloc NULL check.",
            },
            "constraints": [
                "I2C bus frequency: 400 kHz (Fast Mode)",
                "Task must not block the I2C bus for more than 5 ms",
                "Use mutex to protect shared I2C bus resource",
            ],
        }

    # ------------------------------------------------------------------ SPI
    elif "spi" in msg_lower:
        spec = {
            "mcu": "ESP32",
            "rtos": "FreeRTOS",
            "peripherals": [
                {
                    "name": "SPI_Device",
                    "interface": "SPI",
                    "pins": {
                        "MOSI": "GPIO23",
                        "MISO": "GPIO19",
                        "SCLK": "GPIO18",
                        "CS": "GPIO5",
                    },
                }
            ],
            "tasks": [
                {
                    "name": "spi_transfer_task",
                    "priority": 6,
                    "stack_size": 4096,
                    "period_ms": 50,
                    "description": "Perform DMA-backed SPI transfers at 50 ms intervals.",
                }
            ],
            "memory": {"heap_kb": 16, "stack_kb": 4, "notes": "DMA buffers must be in DMA-capable memory region."},
            "constraints": [
                "SPI clock: 10 MHz",
                "CS line held low for entire transaction",
                "Use SPI semaphore for thread safety",
            ],
        }

    # ------------------------------------------------------------------ UART
    elif "uart" in msg_lower or "serial" in msg_lower:
        spec = {
            "mcu": "STM32F4",
            "rtos": "FreeRTOS",
            "peripherals": [
                {
                    "name": "UART2",
                    "interface": "UART",
                    "pins": {"TX": "PA2", "RX": "PA3"},
                    "baud_rate": 115200,
                }
            ],
            "tasks": [
                {
                    "name": "uart_rx_task",
                    "priority": 7,
                    "stack_size": 2048,
                    "period_ms": 0,
                    "description": "Block on UART RX queue; parse incoming packets.",
                },
                {
                    "name": "uart_tx_task",
                    "priority": 6,
                    "stack_size": 2048,
                    "period_ms": 20,
                    "description": "Dequeue and transmit outgoing packets every 20 ms.",
                },
            ],
            "memory": {
                "heap_kb": 8,
                "stack_kb": 4,
                "notes": "Circular DMA receive buffer; ring-buffer implementation recommended.",
            },
            "constraints": [
                "Baud rate: 115200",
                "8-N-1 framing",
                "Use FreeRTOS stream buffer for zero-copy data transfer",
            ],
        }

    # ------------------------------------------------------------------ GPIO
    elif "gpio" in msg_lower or "led" in msg_lower or "button" in msg_lower:
        spec = {
            "mcu": "ESP32",
            "rtos": "FreeRTOS",
            "peripherals": [
                {"name": "LED", "interface": "GPIO", "pins": {"ANODE": "GPIO2"}, "active_high": True},
                {"name": "BUTTON", "interface": "GPIO", "pins": {"INPUT": "GPIO0"}, "pull_up": True},
            ],
            "tasks": [
                {
                    "name": "blink_task",
                    "priority": 3,
                    "stack_size": 1024,
                    "period_ms": 500,
                    "description": "Toggle LED every 500 ms.",
                },
                {
                    "name": "button_task",
                    "priority": 4,
                    "stack_size": 1024,
                    "period_ms": 10,
                    "description": "Debounce button; post event to queue on press.",
                },
            ],
            "memory": {"heap_kb": 4, "stack_kb": 2, "notes": "Minimal memory footprint; no heap allocation required."},
            "constraints": [
                "Debounce time: 20 ms",
                "Button interrupt on falling edge",
                "LED PWM via LEDC peripheral for brightness control",
            ],
        }

    # ------------------------------------------------------------------ ADC
    elif "adc" in msg_lower or "sensor" in msg_lower or "temperature" in msg_lower:
        spec = {
            "mcu": "STM32F4",
            "rtos": "FreeRTOS",
            "peripherals": [
                {
                    "name": "ADC1_CH0",
                    "interface": "ADC",
                    "pins": {"INPUT": "PA0"},
                    "resolution_bits": 12,
                    "vref_mv": 3300,
                }
            ],
            "tasks": [
                {
                    "name": "adc_sample_task",
                    "priority": 6,
                    "stack_size": 2048,
                    "period_ms": 100,
                    "description": "Sample ADC at 10 Hz; apply moving-average filter; post result to data queue.",
                }
            ],
            "memory": {
                "heap_kb": 8,
                "stack_kb": 2,
                "notes": "Moving-average window (16 samples) allocated statically.",
            },
            "constraints": [
                "ADC sampling rate: 10 Hz",
                "Apply 16-point moving average",
                "Trigger via TIM2 hardware timer for precise timing",
            ],
        }

    # ------------------------------------------------------------------ Default / generic
    else:
        spec = {
            "mcu": "ESP32",
            "rtos": "FreeRTOS",
            "peripherals": [
                {
                    "name": "Generic_Peripheral",
                    "interface": "Unknown",
                    "pins": {},
                    "notes": "No specific peripheral detected; using generic template.",
                }
            ],
            "tasks": [
                {
                    "name": "main_task",
                    "priority": 5,
                    "stack_size": 4096,
                    "period_ms": 1000,
                    "description": "Generic main application task.",
                }
            ],
            "memory": {
                "heap_kb": 16,
                "stack_kb": 4,
                "notes": "Default memory allocation; adjust after profiling.",
            },
            "constraints": ["Follow ESP-IDF coding standards", "All tasks must call vTaskDelete(NULL) on exit"],
        }

    return json.dumps(spec, indent=2)


# ---------------------------------------------------------------------------
# Planner Agent
# ---------------------------------------------------------------------------

class PlannerAgent:
    """
    Converts a natural-language task description into a structured
    ``HardwareSpec`` dictionary.

    Parameters
    ----------
    llm_backend:
        Callable with signature ``(system_prompt: str, user_message: str) -> str``
        that returns a JSON string conforming to the ``HardwareSpec`` schema.
        Defaults to ``mock_zhipu_call``.
    """

    SYSTEM_PROMPT = (
        "You are an expert Embedded Systems Architect specialising in RTOS-based "
        "microcontrollers (ESP32, STM32).  "
        "When given a natural-language task description you MUST respond with a "
        "single, valid JSON object that conforms exactly to the HardwareSpec schema.  "
        "Include every field: mcu, rtos, peripherals, tasks, memory, constraints.  "
        "Do NOT include any prose outside the JSON object."
    )

    def __init__(self, llm_backend=None):
        self._llm = llm_backend or mock_zhipu_call

    # ------------------------------------------------------------------
    def plan(self, user_request: str) -> HardwareSpec:
        """
        Execute the planning step.

        Parameters
        ----------
        user_request:
            Free-form description of the embedded task, e.g.
            "Setup an I2C task for an OLED display with FreeRTOS".

        Returns
        -------
        HardwareSpec
            Parsed hardware specification dictionary.

        Raises
        ------
        ValueError
            If the LLM response cannot be parsed as valid JSON.
        """
        raw_response = self._llm(self.SYSTEM_PROMPT, user_request)

        # Strip markdown code fences if the model wraps the JSON
        cleaned = re.sub(r"```(?:json)?\s*", "", raw_response).strip()

        try:
            spec: HardwareSpec = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"PlannerAgent: LLM returned invalid JSON.\n"
                f"Raw response:\n{raw_response}\n"
                f"Parse error: {exc}"
            ) from exc

        self._validate_spec(spec)
        return spec

    # ------------------------------------------------------------------
    @staticmethod
    def _validate_spec(spec: HardwareSpec) -> None:
        """Raise ``ValueError`` if mandatory top-level keys are absent."""
        required_keys = {"mcu", "rtos", "peripherals", "tasks", "memory", "constraints"}
        missing = required_keys - set(spec.keys())
        if missing:
            raise ValueError(
                f"PlannerAgent: Hardware spec is missing required keys: {missing}"
            )
