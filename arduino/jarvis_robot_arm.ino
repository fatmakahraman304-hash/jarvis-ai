/*
  JARVIS robot kol — Arduino (Uno/Nano/Mega) veya ESP32 (seri bağlantı)
  JARVIS şu komutu gönderir:  S<taban>,<omuz>,<dirsek>,<bilek>,<kıskaç>\n   (açılar 0-180)
  Örnek:  S90,120,45,90,20

  Bağlantı (servo sinyal pinleri): taban=3, omuz=5, dirsek=6, bilek=9, kıskaç=10
  Servoları Arduino 5V'undan DEĞİL, ayrı 5-6V güç kaynağından besle; GND'leri birleştir.
  Seri hız: 115200 (JARVIS Ayarlar > Robot kol: port örn. COM3)
*/
#include <Servo.h>

const int PINS[5] = {3, 5, 6, 9, 10};
const int MIN_A[5] = {0, 15, 0, 0, 10};     // mekanik sınırlar (kendi koluna göre ayarla)
const int MAX_A[5] = {180, 165, 180, 180, 100};
Servo servo[5];
float cur[5] = {90, 90, 90, 90, 90};
int target[5] = {90, 90, 90, 90, 90};
String line;

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 5; i++) { servo[i].attach(PINS[i]); servo[i].write(90); }
  Serial.println("JARVIS_ARM_READY");
}

void parse(const String &s) {
  if (s.length() < 2 || s[0] != 'S') return;
  int idx = 0, start = 1;
  for (int i = 1; i <= (int)s.length() && idx < 5; i++) {
    if (i == (int)s.length() || s[i] == ',') {
      int v = s.substring(start, i).toInt();
      target[idx] = constrain(v, MIN_A[idx], MAX_A[idx]);
      idx++; start = i + 1;
    }
  }
  Serial.print("OK ");
  for (int i = 0; i < 5; i++) { Serial.print(target[i]); Serial.print(i < 4 ? "," : "\n"); }
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { parse(line); line = ""; }
    else if (c != '\r' && line.length() < 40) line += c;
  }
  // yumuşak hareket: her adımda hedefe %15 yaklaş
  for (int i = 0; i < 5; i++) {
    cur[i] += (target[i] - cur[i]) * 0.15;
    servo[i].write((int)cur[i]);
  }
  delay(15);
}
