/*
 * ESP32-CAM — WiFi MJPEG Stream
 *
 * Board: AI Thinker ESP32-CAM  (Tools -> Board -> AI Thinker ESP32-CAM)
 * Upload: requires FTDI programmer, GPIO0 pulled LOW during upload, then HIGH to run
 *
 * Once running, open Serial Monitor at 115200 to see the stream URL.
 * app.py connects with: cv2.VideoCapture("http://<camera_ip>/stream")
 *
 * For two cameras: flash the same sketch to both, they each get their own IP.
 */

#include "esp_camera.h"
#include <WiFi.h>

#define CAMERA_MODEL_AI_THINKER  // must be defined before camera_pins.h
#include "camera_pins.h"

// ---- WiFi credentials ----
const char* WIFI_SSID = "Bryan_phone";
const char* WIFI_PASS = "bryan123";
// --------------------------

WiFiServer server(80);

void startCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_VGA;   // 640x480 — change to FRAMESIZE_QVGA for faster stream
  config.jpeg_quality = 12;              // 0=best, 63=worst
  config.fb_count     = 2;
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.grab_mode    = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed — check wiring");
    while (true) delay(1000);
  }
  Serial.println("Camera ready");
}

void setup() {
  Serial.begin(115200);

  startCamera();

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
  }
  Serial.println("\nConnected! Stream URL: http://" + WiFi.localIP().toString() + "/stream");

  server.begin();
}

void streamTo(WiFiClient client) {
  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
  client.println("Connection: keep-alive");
  client.println();

  while (client.connected()) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Frame capture failed");
      continue;
    }

    client.printf("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
    client.write(fb->buf, fb->len);
    client.println();

    esp_camera_fb_return(fb);
  }
}

void loop() {
  WiFiClient client = server.accept();
  if (!client) return;

  // Read the HTTP request line
  String req = client.readStringUntil('\n');

  if (req.startsWith("GET /stream")) {
    streamTo(client);
  } else {
    // Any other request: return a simple link to the stream
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: text/html");
    client.println();
    client.println("<a href='/stream'>stream</a>");
  }

  client.stop();
}
