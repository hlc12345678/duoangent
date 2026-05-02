from __future__ import annotations

from textwrap import dedent
from typing import List, Optional

from .planner_agent import HardwareSpec


def mock_doubao_call(spec: HardwareSpec, feedback: Optional[List[str]] = None) -> str:
    feedback_text = " ".join(feedback or [])
    uses_timeout = "timeout" in feedback_text.lower()
    timeout_ticks = "pdMS_TO_TICKS(200)" if uses_timeout else "portMAX_DELAY"

    if spec.target_mcu == "STM32":
        return dedent(
            f"""
            #include "main.h"
            #include "cmsis_os.h"

            #define I2C_SCL_PIN {spec.pins.get("SCL", "PB8")}
            #define I2C_SDA_PIN {spec.pins.get("SDA", "PB9")}

            static I2C_HandleTypeDef hi2c1;
            static uint8_t display_buffer[128];
            static SemaphoreHandle_t i2c_mutex;

            static void MX_I2C1_Init(void) {{
                hi2c1.Instance = I2C1;
                hi2c1.Init.ClockSpeed = 400000;
                hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
                hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
                HAL_I2C_Init(&hi2c1);
            }}

            static void DisplayTask(void *argument) {{
                for (;;) {{
                    if (xSemaphoreTake(i2c_mutex, {timeout_ticks}) == pdTRUE) {{
                        HAL_I2C_Master_Transmit(&hi2c1, 0x78, display_buffer, sizeof(display_buffer), 100);
                        xSemaphoreGive(i2c_mutex);
                    }}
                    osDelay(100);
                }}
            }}

            void StartDefaultTask(void *argument) {{
                MX_I2C1_Init();
                i2c_mutex = xSemaphoreCreateMutex();
                xTaskCreate(DisplayTask, "display", 512, NULL, osPriorityNormal, NULL);
                for (;;) {{
                    osDelay(1000);
                }}
            }}
            """
        ).strip()

    return dedent(
        f"""
        #include <string.h>
        #include "driver/i2c.h"
        #include "freertos/FreeRTOS.h"
        #include "freertos/task.h"
        #include "freertos/semphr.h"

        #define I2C_MASTER_SCL_IO {spec.pins.get("SCL", "GPIO22")}
        #define I2C_MASTER_SDA_IO {spec.pins.get("SDA", "GPIO21")}
        #define I2C_MASTER_NUM I2C_NUM_0
        #define I2C_MASTER_FREQ_HZ 400000
        #define OLED_ADDR 0x3C

        static SemaphoreHandle_t i2c_mutex;
        static uint8_t display_frame[128];

        static void i2c_master_init(void) {{
            i2c_config_t conf = {{
                .mode = I2C_MODE_MASTER,
                .sda_io_num = I2C_MASTER_SDA_IO,
                .scl_io_num = I2C_MASTER_SCL_IO,
                .sda_pullup_en = GPIO_PULLUP_ENABLE,
                .scl_pullup_en = GPIO_PULLUP_ENABLE,
                .master.clk_speed = I2C_MASTER_FREQ_HZ,
            }};
            i2c_param_config(I2C_MASTER_NUM, &conf);
            i2c_driver_install(I2C_MASTER_NUM, conf.mode, 0, 0, 0);
        }}

        static void display_update_task(void *pvParameters) {{
            (void)pvParameters;
            for (;;) {{
                if (xSemaphoreTake(i2c_mutex, {timeout_ticks}) == pdTRUE) {{
                    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
                    i2c_master_start(cmd);
                    i2c_master_write_byte(cmd, (OLED_ADDR << 1) | I2C_MASTER_WRITE, true);
                    i2c_master_write(cmd, display_frame, sizeof(display_frame), true);
                    i2c_master_stop(cmd);
                    i2c_master_cmd_begin(I2C_MASTER_NUM, cmd, pdMS_TO_TICKS(50));
                    i2c_cmd_link_delete(cmd);
                    xSemaphoreGive(i2c_mutex);
                }}
                vTaskDelay(pdMS_TO_TICKS(100));
            }}
        }}

        void app_main(void) {{
            i2c_master_init();
            i2c_mutex = xSemaphoreCreateMutex();
            xTaskCreate(display_update_task, "display_update", 4096, NULL, 5, NULL);
        }}
        """
    ).strip()


def generate_code(spec: HardwareSpec) -> str:
    return mock_doubao_call(spec)


def revise_code(spec: HardwareSpec, previous_code: str, feedback: List[str]) -> str:
    if not feedback:
        return previous_code
    return mock_doubao_call(spec, feedback)
