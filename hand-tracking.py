import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import cv2
import numpy as np
import math
import urllib.request
import mediapipe as mp

# ---------------------------------------------------------
# Download MediaPipe Hand Landmarker model automatically
# ---------------------------------------------------------

MODEL_PATH = "hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/"
    "hand_landmarker.task"
)

if not os.path.exists(MODEL_PATH):
    print("Downloading MediaPipe hand model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Model downloaded successfully.")

# ---------------------------------------------------------
# MediaPipe Tasks API
# ---------------------------------------------------------

BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.IMAGE,
    num_hands=2,
    min_hand_detection_confidence=0.3,
    min_hand_presence_confidence=0.3,
    min_tracking_confidence=0.3
)

landmarker = HandLandmarker.create_from_options(options)

# ---------------------------------------------------------
# Camera
# ---------------------------------------------------------

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    raise RuntimeError("Could not open camera.")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

cv2.namedWindow("Hand Tracking with Drawing", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Hand Tracking with Drawing", 1280, 720)

ret, frame = cap.read()

if not ret:
    cap.release()
    raise RuntimeError("Could not read camera frame.")

frame_height, frame_width = frame.shape[:2]

canvas = np.zeros(
    (frame_height, frame_width, 3),
    dtype=np.uint8
)

# ---------------------------------------------------------
# Settings
# ---------------------------------------------------------

tracking_enabled = True
drawing = False

drawing_colors = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (255, 255, 255),
    (0, 0, 0)
]

selected_color = (255, 255, 255)

finger_names = [
    "Thumb",
    "Index",
    "Middle",
    "Ring",
    "Pinky"
]

# MediaPipe landmark indexes
finger_indices = {
    "Thumb": [1, 2, 3, 4],
    "Index": [5, 6, 7, 8],
    "Middle": [9, 10, 11, 12],
    "Ring": [13, 14, 15, 16],
    "Pinky": [17, 18, 19, 20]
}

# ---------------------------------------------------------
# Angle calculation
# ---------------------------------------------------------

def calculate_angle(p1, p2, p3):
    angle = math.degrees(
        math.atan2(p3.y - p2.y, p3.x - p2.x)
        -
        math.atan2(p1.y - p2.y, p1.x - p2.x)
    )

    angle = abs(angle)

    if angle > 180:
        angle = 360 - angle

    return angle


# ---------------------------------------------------------
# Finger up/down detection
# ---------------------------------------------------------

def fingers_up(hand_landmarks):
    up = []

    for finger in finger_names:
        indexes = finger_indices[finger]

        p2 = hand_landmarks[indexes[1]]
        p3 = hand_landmarks[indexes[2]]
        p4 = hand_landmarks[indexes[3]]

        angle = calculate_angle(p2, p3, p4)

        if angle > 150:
            up.append(1)
        else:
            up.append(0)

    return up


# ---------------------------------------------------------
# Draw hand landmarks
# ---------------------------------------------------------

def draw_hand(frame, landmarks):

    connections = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (17, 18), (18, 19), (19, 20),
        (0, 17)
    ]

    points = []

    for landmark in landmarks:
        x = int(landmark.x * frame_width)
        y = int(landmark.y * frame_height)

        points.append((x, y))

        cv2.circle(
            frame,
            (x, y),
            5,
            (0, 255, 0),
            -1
        )

    for start, end in connections:
        cv2.line(
            frame,
            points[start],
            points[end],
            (255, 255, 255),
            2
        )

    return points


# ---------------------------------------------------------
# Main loop
# ---------------------------------------------------------

while True:

    ret, frame = cap.read()

    if not ret:
        break

    frame = cv2.flip(frame, 1)

    # RGB image for MediaPipe
    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    # Detect hands
    if tracking_enabled:

        result = landmarker.detect(mp_image)

        if result.hand_landmarks:

            combined_total_up = 0

            for hand_index, hand_landmarks in enumerate(result.hand_landmarks):

                if result.handedness:
                    hand_label = result.handedness[hand_index][0].category_name
                else:
                    hand_label = "Right"

                points = draw_hand(
                    frame,
                    hand_landmarks
                )

                # -------------------------------------------------
                # Finger movement / up-down status
                # -------------------------------------------------

                finger_status = fingers_up(hand_landmarks)
                total_up = sum(finger_status)
                combined_total_up += total_up

                column_x = 50 if hand_index == 0 else frame_width - 220

                cv2.putText(
                    frame,
                    f"{hand_label} Hand Up: {total_up}",
                    (column_x, 320),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2
                )

                for i, name in enumerate(finger_names):
                    status = "Up" if finger_status[i] else "Down"
                    cv2.putText(
                        frame,
                        f"{name}: {status}",
                        (column_x, 360 + i * 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 255),
                        1
                    )

                # -------------------------------------------------
                # Index finger tip
                # -------------------------------------------------

                index_tip = hand_landmarks[8]

                x = int(index_tip.x * frame_width)
                y = int(index_tip.y * frame_height)

                # Drawing
                if drawing and y >= 50:

                    cv2.circle(
                        canvas,
                        (x, y),
                        5,
                        selected_color,
                        -1
                    )

                # -------------------------------------------------
                # Color selection
                # -------------------------------------------------

                if y < 50:

                    color_index = x // 50

                    if 0 <= color_index < len(drawing_colors):

                        selected_color = drawing_colors[
                            color_index
                        ]

                # -------------------------------------------------
                # Detect bent fingers
                # -------------------------------------------------

                for finger, indexes in finger_indices.items():

                    p1 = hand_landmarks[indexes[0]]
                    p2 = hand_landmarks[indexes[1]]
                    p3 = hand_landmarks[indexes[2]]
                    p4 = hand_landmarks[indexes[3]]

                    angle1 = calculate_angle(
                        p1,
                        p2,
                        p3
                    )

                    angle2 = calculate_angle(
                        p2,
                        p3,
                        p4
                    )

                    if angle1 < 85 and angle2 < 85:

                        finger_position = (
                            100
                            + finger_names.index(finger) * 45
                        )

                        cv2.putText(
                            frame,
                            f"{finger} bent",
                            (50, finger_position),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            selected_color,
                            2
                        )

            cv2.putText(
                frame,
                f"Total Fingers Up: {combined_total_up}",
                (50, 290),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2
            )

    # ---------------------------------------------------------
    # Color bar
    # ---------------------------------------------------------

    for i, color in enumerate(drawing_colors):

        cv2.rectangle(
            frame,
            (i * 50, 0),
            ((i + 1) * 50, 50),
            color,
            -1
        )

    # ---------------------------------------------------------
    # Combine camera + drawing canvas
    # ---------------------------------------------------------

    output = cv2.addWeighted(
        frame,
        0.5,
        canvas,
        0.5,
        0
    )

    cv2.imshow(
        "Hand Tracking with Drawing",
        output
    )

    # ---------------------------------------------------------
    # Keyboard controls
    # ---------------------------------------------------------

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

    elif key == ord("t"):
        tracking_enabled = not tracking_enabled

    elif key == ord("d"):
        drawing = not drawing

    elif key == ord("c"):
        canvas[:] = 0


# ---------------------------------------------------------
# Cleanup
# ---------------------------------------------------------

cap.release()
landmarker.close()
cv2.destroyAllWindows()
