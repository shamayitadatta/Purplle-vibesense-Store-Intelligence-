import cv2
import numpy as np
import os

os.makedirs("data/cctv_footage", exist_ok=True)
out = cv2.VideoWriter('data/cctv_footage/sample.mp4', cv2.VideoWriter_fourcc(*'mp4v'), 15, (640, 480))
for i in range(30):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # draw something
    cv2.putText(frame, f"Frame {i}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    out.write(frame)
out.release()
