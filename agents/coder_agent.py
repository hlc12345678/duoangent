from __future__ import annotations

from string import Template
from textwrap import dedent
from typing import List, Optional

from .planner_agent import HardwareSpec


def mock_llm_call(spec: HardwareSpec, feedback: Optional[List[str]] = None) -> str:
    feedback_text = " ".join(feedback or [])
    uses_timeout = "timeout" in feedback_text.lower()
    timeout_ticks = "pdMS_TO_TICKS(200)" if uses_timeout else "portMAX_DELAY"

    if spec.target_mcu == "STM32":
        template = Template(
            dedent(
                """
                #include "main.h"
                #include "cmsis_os.h"
                #include "FreeRTOS.h"
                #include "task.h"

                #define I2C_SCL_PIN $SCL_PIN
                #define I2C_SDA_PIN $SDA_PIN

                static I2C_HandleTypeDef hi2c1;
                static uint8_t display_buffer[128];
                static SemaphoreHandle_t i2c_mutex;

                static void MX_I2C1_Init(void) {
                    hi2c1.Instance = I2C1;
                    hi2c1.Init.ClockSpeed = 400000;
                    hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
                    hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
                    HAL_I2C_Init(&hi2c1);
                }

                static void DisplayTask(void *argument) {
                    for (;;) {
                        if (xSemaphoreTake(i2c_mutex, $TIMEOUT_TICKS) == pdTRUE) {
                            HAL_I2C_Master_Transmit(&hi2c1, 0x78, display_buffer, sizeof(display_buffer), 100);
                            xSemaphoreGive(i2c_mutex);
                        }
                        osDelay(100);
                    }
                }

                void StartDefaultTask(void *argument) {
                    MX_I2C1_Init();
                    i2c_mutex = xSemaphoreCreateMutex();
                    if (i2c_mutex == NULL) {
                        return;
                    }
                    if (xTaskCreate(DisplayTask, "display", 512, NULL, osPriorityNormal, NULL) != pdPASS) {
                        return;
                    }
                    for (;;) {
                        osDelay(1000);
                    }
                }
                """
            )
        )
        return template.substitute(
            SCL_PIN=spec.pins.get("SCL", "PB8"),
            SDA_PIN=spec.pins.get("SDA", "PB9"),
            TIMEOUT_TICKS=timeout_ticks,
        ).strip()

    template = Template(
        dedent(
            """
            #include <string.h>
            #include "driver/i2c.h"
            #include "esp_err.h"
            #include "freertos/FreeRTOS.h"
            #include "freertos/task.h"
            #include "freertos/semphr.h"

            #define I2C_MASTER_SCL_IO $SCL_PIN
            #define I2C_MASTER_SDA_IO $SDA_PIN
            #define I2C_MASTER_NUM I2C_NUM_0
            #define I2C_MASTER_FREQ_HZ 400000
            #define OLED_ADDR 0x3C

            static SemaphoreHandle_t i2c_mutex;
            static uint8_t display_frame[128];

            static void i2c_master_init(void) {
                i2c_config_t conf = {
                    .mode = I2C_MODE_MASTER,
                    .sda_io_num = I2C_MASTER_SDA_IO,
                    .scl_io_num = I2C_MASTER_SCL_IO,
                    .sda_pullup_en = GPIO_PULLUP_ENABLE,
                    .scl_pullup_en = GPIO_PULLUP_ENABLE,
                    .master.clk_speed = I2C_MASTER_FREQ_HZ,
                };
                i2c_param_config(I2C_MASTER_NUM, &conf);
                i2c_driver_install(I2C_MASTER_NUM, conf.mode, 0, 0, 0);
            }

            static void display_update_task(void *pvParameters) {
                (void)pvParameters;
                for (;;) {
                    if (xSemaphoreTake(i2c_mutex, $TIMEOUT_TICKS) == pdTRUE) {
                        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
                        if (cmd == NULL) {
                            xSemaphoreGive(i2c_mutex);
                            vTaskDelay(pdMS_TO_TICKS(50));
                            continue;
                        }
                        i2c_master_start(cmd);
                        i2c_master_write_byte(cmd, (OLED_ADDR << 1) | I2C_MASTER_WRITE, true);
                        i2c_master_write(cmd, display_frame, sizeof(display_frame), true);
                        i2c_master_stop(cmd);
                        esp_err_t ret = i2c_master_cmd_begin(
                            I2C_MASTER_NUM,
                            cmd,
                            pdMS_TO_TICKS(50)
                        );
                        i2c_cmd_link_delete(cmd);
                        if (ret != ESP_OK) {
                            xSemaphoreGive(i2c_mutex);
                            vTaskDelay(pdMS_TO_TICKS(50));
                            continue;
                        }
                        xSemaphoreGive(i2c_mutex);
                    }
                    vTaskDelay(pdMS_TO_TICKS(100));
                }
            }

            void app_main(void) {
                i2c_master_init();
                i2c_mutex = xSemaphoreCreateMutex();
                if (i2c_mutex == NULL) {
                    return;
                }
                if (xTaskCreate(display_update_task, "display_update", 4096, NULL, 5, NULL) != pdPASS) {
                    return;
                }
            }
            """
        )
    )
    return template.substitute(
        SCL_PIN=spec.pins.get("SCL", "GPIO22"),
        SDA_PIN=spec.pins.get("SDA", "GPIO21"),
        TIMEOUT_TICKS=timeout_ticks,
    ).strip()


def generate_code(spec: HardwareSpec) -> str:
    return mock_llm_call(spec)


def revise_code(spec: HardwareSpec, previous_code: str, feedback: List[str]) -> str:
    if not feedback:
        return previous_code
    updated_code = mock_llm_call(spec, feedback)
    return updated_code or previous_code

