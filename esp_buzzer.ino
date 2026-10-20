#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* ssid = "YOUR_SSID";
const char* password = "YOUR_PASSWORD";
const int BUZZ_PIN = 13; // change to your buzzer pin
const String AUTH_TOKEN = "your-secret-token";

WebServer server(80);

void buzzHandler() {
  if (server.method() != HTTP_POST) { server.send(405); return; }
  String body = server.arg("plain");
  StaticJsonDocument<200> doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) { server.send(400); return; }
  String token = "";
  int duration = 500;
  if (doc.containsKey("token")) token = String((const char*)doc["token"]);
  if (doc.containsKey("duration_ms")) duration = doc["duration_ms"];
  if (token != AUTH_TOKEN) { server.send(401); return; }
  digitalWrite(BUZZ_PIN, HIGH);
  delay(duration);
  digitalWrite(BUZZ_PIN, LOW);
  server.send(200, "application/json", "{\"status\":\"ok\"}");
}

void setup() {
  Serial.begin(115200);
  pinMode(BUZZ_PIN, OUTPUT);
  digitalWrite(BUZZ_PIN, LOW);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println(WiFi.localIP());
  server.on("/buzz", buzzHandler);
  server.begin();
}

void loop() {
  server.handleClient();
}
