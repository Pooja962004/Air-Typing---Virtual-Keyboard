import os, ctypes, cv2, time
import numpy as np
from cvzone.HandTrackingModule import HandDetector
from pynput.keyboard import Controller, Key
import speech_recognition as sr
from PIL import Image, ImageFont
from pilmoji import Pilmoji

# Suppress logs
os.environ.update({'TF_CPP_MIN_LOG_LEVEL':'3','GLOG_minloglevel':'2'})

# Full screen resolution
user32 = ctypes.windll.user32
W, H = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

# Initialize modules
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
detector = HandDetector(detectionCon=0.8, maxHands=1)
kb = Controller()
font = ImageFont.truetype("arial.ttf", 36)

# Keyboard layout
KEYS = [list("1234567890-="), list("QWERTYUIOP[]\\"), list("ASDFGHJKL;'"), list("ZXCVBNM,./")]
SPECIALS = ["Back", "Enter", "Emoji", "Space"]
EMOJIS = ["😄", "❤", "🎉", "👍", "😂", "🥰"]

class Button:
    def __init__(self, pos, text, size):
        self.pos, self.text, self.size = pos, text, size

buttons, emojis = [], []
key_w, key_h = W // 14, int((W // 14) * 0.8)

for r, row in enumerate(KEYS):
    for c, k in enumerate(row):
        buttons.append(Button([10 + c * key_w, 10 + r * (key_h + 10)], k, [key_w - 5, key_h]))
for i, k in enumerate(SPECIALS):
    buttons.append(Button([10 + i * (W // 4), 10 + 4 * (key_h + 10)], k, [(W // 4) - 15, key_h]))
for i, e in enumerate(EMOJIS):
    emojis.append(Button([10 + i * key_w, H - key_h - 150], e, [key_w - 5, key_h]))

# App state
final_text = ""
emoji_mode = False
keyboard_visible = True
last_tap = None
prev_y = None
ready = False
TAP_DOWN, TAP_UP = 15, -10

# Evaluation metrics
start_time = time.time()
total_taps = 0
correct_taps = 0

# Voice Recognition Setup
r = sr.Recognizer()
r.pause_threshold = 0.5
r.energy_threshold = 300
r.dynamic_energy_threshold = True

def callback(recognizer, audio):
    global keyboard_visible
    try:
        cmd = recognizer.recognize_google(audio).lower()
        if "show keyboard" in cmd:
            keyboard_visible = True
        elif "hide keyboard" in cmd:
            keyboard_visible = False
        elif "exit keyboard" in cmd:
            os._exit(0)
    except:
        pass

mic = sr.Microphone()
with mic as source:
    r.adjust_for_ambient_noise(source, duration=0.5)
stop_listening = r.listen_in_background(mic, callback)

# OpenCV window
cv2.namedWindow("Air Keyboard", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("Air Keyboard", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

while True:
    ret, frame = cap.read()
    if not ret: break

    frame = cv2.flip(frame, 1)
    frame = cv2.resize(frame, (W, H))
    hands, frame = detector.findHands(frame, draw=False)

    finger_pos = None
    if hands:
        finger_pos = hands[0]['lmList'][8][:2]

    if keyboard_visible:
        overlay = frame.copy()

        # Render main keys
        for b in buttons:
            x, y = b.pos; w, h = b.size
            is_hover = finger_pos and x < finger_pos[0] < x + w and y < finger_pos[1] < y + h
            cv2.rectangle(overlay, (x, y), (x + w, y + h),
                          (255,144,30) if is_hover else (200,200,255), cv2.FILLED)
            cv2.rectangle(overlay, (x, y), (x + w, y + h),
                          (255,144,30), 2)
            cv2.putText(overlay, b.text, (x + 10, y + int(h * 0.6)),
                        cv2.FONT_HERSHEY_PLAIN, 2, (0,0,0), 2)

        # Render emojis if active
        if emoji_mode:
            for b in emojis:
                x, y = b.pos; w, h = b.size
                is_hover = finger_pos and x < finger_pos[0] < x + w and y < finger_pos[1] < y + h
                cv2.rectangle(overlay, (x, y), (x + w, y + h),
                              (255,144,30) if is_hover else (144,255,200), cv2.FILLED)
                cv2.rectangle(overlay, (x, y), (x + w, y + h),
                              (255,144,30), 2)
                cv2.putText(overlay, b.text, (x + 10, y + int(h * 0.6)),
                            cv2.FONT_HERSHEY_PLAIN, 2, (0,0,0), 2)

        frame = cv2.addWeighted(frame, 0.6, overlay, 0.4, 0)

        # Tap typing logic
        if hands:
            x1, y1 = finger_pos
            cv2.circle(frame, (x1, y1), 12, (255, 144, 30), cv2.FILLED)
            if prev_y is not None:
                dy = y1 - prev_y
                if dy > TAP_DOWN:
                    ready = True
                elif ready and dy < TAP_UP and time.time() - (last_tap or 0) > 0.3:
                    pool = emojis if emoji_mode else buttons
                    total_taps += 1  # track tap attempt
                    tapped = False
                    for b in pool:
                        x, y = b.pos; w, h = b.size
                        if x < x1 < x + w and y < y1 < y + h:
                            key = b.text
                            tapped = True
                            correct_taps += 1
                            if key == "Back":
                                kb.press(Key.backspace); kb.release(Key.backspace)
                                final_text = final_text[:-1]
                            elif key == "Enter":
                                kb.press(Key.enter); kb.release(Key.enter)
                                final_text += "\n"
                            elif key == "Space":
                                kb.type(" "); final_text += " "
                            elif key == "Emoji":
                                emoji_mode = not emoji_mode
                            else:
                                kb.type(key); final_text += key
                                emoji_mode = False

                            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 100, 255), cv2.FILLED)
                            cv2.putText(frame, key, (x + 10, y + int(h * 0.6)),
                                        cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)
                            last_tap = time.time()
                            break
                    if not tapped:
                        last_tap = time.time()
                    ready = False
            prev_y = y1

        # Draw text box
        tb = H - 130
        cv2.rectangle(frame, (10, tb), (W - 10, tb + 100), (0, 0, 0), cv2.FILLED)
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        with Pilmoji(pil) as pm:
            pm.text((20, tb + 10), final_text, (255, 255, 255), font=font)
        frame = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

        # Calculate & display evaluation metrics
        elapsed_minutes = (time.time() - start_time) / 60
        num_words = len(final_text.strip().split())
        wpm = num_words / elapsed_minutes if elapsed_minutes > 0 else 0
        accuracy = (correct_taps / total_taps * 100) if total_taps > 0 else 0

        cv2.putText(frame, f"WPM: {wpm:.1f}", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
        cv2.putText(frame, f"Accuracy: {accuracy:.1f}%", (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

    cv2.imshow("Air Keyboard", frame)
    if cv2.waitKey(1) == ord('q'):
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
stop_listening()
