/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <inttypes.h>
#include <string.h>
#include "esp_log.h"
#include "esp_system.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_event.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_hosted.h"
#include "esp_hosted_misc.h"
#include "esp_hosted_ota.h"
#include "esp_timer.h"
#include "esp_app_desc.h"
#include "esp_hosted_api_types.h"

#if CONFIG_OTA_METHOD_HTTPS
#include "ota_https.h"
#elif CONFIG_OTA_METHOD_LITTLEFS
#include "ota_littlefs.h"
#elif CONFIG_OTA_METHOD_PARTITION
#include "ota_partition.h"
#endif

static const char *TAG = "host_performs_slave_ota";
static const char *NVS_NAMESPACE = "c6_enabler";
static const char *NVS_VERIFY_KEY = "verify_pending";
static const uint8_t EXPECTED_C6_ELF_SHA256[32] = {
    0x85, 0x54, 0x4a, 0xc1, 0xfa, 0x10, 0xfe, 0xe3,
    0xb6, 0x52, 0x52, 0x51, 0x41, 0xb2, 0xc5, 0x1d,
    0x3a, 0xec, 0xac, 0x89, 0xe5, 0x6e, 0x8d, 0x88,
    0xa4, 0xdd, 0xed, 0x59, 0x4b, 0x56, 0xee, 0xf4,
};

static esp_err_t set_verification_pending(bool pending)
{
    nvs_handle_t handle;
    esp_err_t ret = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (ret != ESP_OK) {
        return ret;
    }

    if (pending) {
        ret = nvs_set_u8(handle, NVS_VERIFY_KEY, 1);
    } else {
        ret = nvs_erase_key(handle, NVS_VERIFY_KEY);
        if (ret == ESP_ERR_NVS_NOT_FOUND) {
            ret = ESP_OK;
        }
    }
    if (ret == ESP_OK) {
        ret = nvs_commit(handle);
    }
    nvs_close(handle);
    return ret;
}

static bool is_verification_pending(void)
{
    nvs_handle_t handle;
    uint8_t pending = 0;
    esp_err_t ret = nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle);
    if (ret != ESP_OK) {
        return false;
    }
    ret = nvs_get_u8(handle, NVS_VERIFY_KEY, &pending);
    nvs_close(handle);
    return ret == ESP_OK && pending == 1;
}

static esp_err_t verify_coprocessor_identity(void)
{
    esp_hosted_app_desc_t desc = { 0 };
    esp_err_t ret = esp_hosted_get_coprocessor_app_desc(&desc);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Could not read running C6 app descriptor: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "Running C6 app: %s %s, IDF %s", desc.project_name, desc.version, desc.idf_ver);
    ESP_LOG_BUFFER_HEX_LEVEL(TAG, desc.app_elf_sha256, sizeof(desc.app_elf_sha256), ESP_LOG_INFO);
    if (memcmp(desc.app_elf_sha256, EXPECTED_C6_ELF_SHA256, sizeof(EXPECTED_C6_ELF_SHA256)) != 0) {
        ESP_LOGE(TAG, "Running C6 ELF identity does not match the packaged firmware");
        return ESP_ERR_INVALID_STATE;
    }

    ESP_LOGI(TAG, "C6_ELF_IDENTITY_VERIFIED");
    return ESP_OK;
}

static esp_err_t verify_coprocessor_espnow(void)
{
    esp_err_t ret = verify_coprocessor_identity();
    if (ret != ESP_OK) {
        return ret;
    }

    wifi_init_config_t wifi_config = WIFI_INIT_CONFIG_DEFAULT();
    ret = esp_wifi_init(&wifi_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "C6 Wi-Fi initialization failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = esp_wifi_set_mode(WIFI_MODE_STA);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "C6 Wi-Fi mode setup failed: %s", esp_err_to_name(ret));
        esp_wifi_deinit();
        return ret;
    }

    ret = esp_wifi_start();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "C6 Wi-Fi startup failed: %s", esp_err_to_name(ret));
        esp_wifi_deinit();
        return ret;
    }

    ret = esp_now_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "C6 ESP-NOW verification failed: %s", esp_err_to_name(ret));
        esp_wifi_stop();
        esp_wifi_deinit();
        return ret;
    }

    ret = esp_now_deinit();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "C6 ESP-NOW cleanup failed: %s", esp_err_to_name(ret));
        esp_wifi_stop();
        esp_wifi_deinit();
        return ret;
    }

    ret = esp_wifi_stop();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "C6 Wi-Fi stop failed: %s", esp_err_to_name(ret));
        esp_wifi_deinit();
        return ret;
    }

    ret = esp_wifi_deinit();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "C6 Wi-Fi cleanup failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "C6_ESPNOW_VERIFIED");
    return ESP_OK;
}

#ifdef CONFIG_OTA_VERSION_CHECK_HOST_SLAVE
/* Compare host and slave firmware versions */
static int compare_self_version_with_slave_version(uint32_t slave_version)
{
    uint32_t host_version = ESP_HOSTED_VERSION_VAL(ESP_HOSTED_VERSION_MAJOR_1,
            ESP_HOSTED_VERSION_MINOR_1,
            ESP_HOSTED_VERSION_PATCH_1);

    // mask out patch level
    // compare major.minor only
    slave_version &= 0xFFFFFF00;
    host_version &= 0xFFFFFF00;

    if (host_version == slave_version) {
        // versions match
        return 0;
    } else if (host_version > slave_version) {
        // host version > slave version
#ifndef CONFIG_ESP_HOSTED_FW_VERSION_MISMATCH_WARNING_SUPPRESS
        ESP_LOGW(TAG, "Version mismatch: Host [%u.%u.%u] > Co-proc [%u.%u.%u] ==> Upgrade co-proc to avoid RPC timeouts",
            ESP_HOSTED_VERSION_PRINTF_ARGS(host_version), ESP_HOSTED_VERSION_PRINTF_ARGS(slave_version));
#endif
        return -1;
    } else {
        // host version < slave version
#ifndef CONFIG_ESP_HOSTED_FW_VERSION_MISMATCH_WARNING_SUPPRESS
        ESP_LOGW(TAG, "Version mismatch: Host [%u.%u.%u] < Co-proc [%u.%u.%u] ==> Upgrade host to avoid compatibility issues",
            ESP_HOSTED_VERSION_PRINTF_ARGS(host_version), ESP_HOSTED_VERSION_PRINTF_ARGS(slave_version));
#endif
        return 1;
    }
}

/* Check host-slave version compatibility */
static int compare_host_slave_version(void)
{
    /* Get slave version via RPC */
    esp_hosted_coprocessor_fwver_t slave_version_struct = {0};
    esp_err_t ret = esp_hosted_get_coprocessor_fwversion(&slave_version_struct);

    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Could not get slave firmware version (error: %s)", esp_err_to_name(ret));
        ESP_LOGW(TAG, "Proceeding without version compatibility check");
        return ESP_OK;
    }

    /* Convert slave version to 32-bit value for comparison */
    uint32_t slave_version = ESP_HOSTED_VERSION_VAL(slave_version_struct.major1,
            slave_version_struct.minor1,
            slave_version_struct.patch1);

    /* Log versions */
    ESP_LOGI(TAG, "Host firmware version: %d.%d.%d", ESP_HOSTED_VERSION_MAJOR_1, ESP_HOSTED_VERSION_MINOR_1, ESP_HOSTED_VERSION_PATCH_1);
    ESP_LOGI(TAG, "Slave firmware version: %" PRIu32 ".%" PRIu32 ".%" PRIu32,
             slave_version_struct.major1, slave_version_struct.minor1, slave_version_struct.patch1);

    return compare_self_version_with_slave_version(slave_version);
}
#endif

void app_main(void)
{
	int ret;

    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_hosted_init());
    ESP_ERROR_CHECK(esp_hosted_connect_to_slave());

    ESP_LOGI(TAG, "ESP-Hosted initialized successfully");

    if (is_verification_pending()) {
        ESP_LOGI(TAG, "Verifying the activated C6 firmware");
        ret = verify_coprocessor_espnow();
        if (ret == ESP_OK) {
            ESP_ERROR_CHECK(set_verification_pending(false));
            ESP_LOGI(TAG, "C6 ESP-NOW installation completed successfully");
        } else {
            ESP_LOGE(TAG, "C6 OTA activation did not produce a working ESP-NOW service");
        }
        return;
    }

#ifdef CONFIG_OTA_VERSION_CHECK_HOST_SLAVE
    /* Check host-slave version compatibility */
    compare_host_slave_version();
#endif

    ESP_LOGW(TAG, "Forcing slave OTA update");

    /* Perform OTA based on Kconfig selection */
#if CONFIG_OTA_METHOD_HTTPS
    ESP_LOGI(TAG, "Using HTTP OTA method");
    ret = ota_https_perform(CONFIG_OTA_SERVER_URL);
#elif CONFIG_OTA_METHOD_LITTLEFS
	uint8_t delete_post_flash = 0;
    ESP_LOGI(TAG, "Using LittleFS OTA method");
  #ifdef CONFIG_OTA_DELETE_FILE_AFTER_FLASH
	delete_post_flash = 1;
  #endif
    ret = ota_littlefs_perform(delete_post_flash);
#elif CONFIG_OTA_METHOD_PARTITION
    ESP_LOGI(TAG, "Using Partition OTA method");
    ret = ota_partition_perform(CONFIG_OTA_PARTITION_LABEL);
#else
    ESP_LOGE(TAG, "No OTA method selected!");
    return;
#endif

    if (ret == ESP_HOSTED_SLAVE_OTA_COMPLETED) {
        ESP_LOGI(TAG, "OTA completed successfully");

        /* Activate the new firmware */
        ESP_ERROR_CHECK(set_verification_pending(true));
        ret = esp_hosted_slave_ota_activate();
        if (ret == ESP_OK) {
            ESP_LOGI(TAG, "Slave will reboot with new firmware");
            ESP_LOGI(TAG, "********* Restarting host to avoid sync issues **********************");
            vTaskDelay(pdMS_TO_TICKS(2000));
            esp_restart();
        } else {
            ESP_ERROR_CHECK(set_verification_pending(false));
            ESP_LOGE(TAG, "Failed to activate OTA: %s", esp_err_to_name(ret));
        }
    } else if (ret == ESP_HOSTED_SLAVE_OTA_NOT_REQUIRED) {
        ESP_LOGI(TAG, "OTA not required");
    } else {
        ESP_LOGE(TAG, "OTA failed: %s", esp_err_to_name(ret));
    }
}
