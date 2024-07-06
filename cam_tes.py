from onvif import ONVIFCamera
import cv2

# # Konfigurasi kamera ONVIF
# camera_host = '192.168.0.130'  # Ganti dengan IP kamera ONVIF Anda
# camera_port = 8000               # Port kamera ONVIF
# camera_user = 'admin'          # Username kamera ONVIF
# camera_pass = 'admin123'      # Password kamera ONVIF
#
# # Inisialisasi koneksi kamera ONVIF
# camera = ONVIFCamera(camera_host, camera_port, camera_user, camera_pass)
#
# # Mendapatkan media service
# media_service = camera.create_media_service()
#
# # Mendapatkan profile media
# profiles = media_service.GetProfiles()
# profile = profiles[0]  # Menggunakan profile pertama
#
# # Mendapatkan stream URI
# stream_uri = media_service.GetStreamUri({
#     'StreamSetup': {
#         'Stream': 'RTP-Unicast',
#         'Transport': {
#             'Protocol': 'RTSP'
#         }
#     },
#     'ProfileToken': profile.token
# })

# {
#     "FirmwareVersion": "ppstrong-c93-tuya2_general-5.5.2.20230531",
#     "HardwareId": "Ver 2.1",
#     "Manufacturer": "PPS IPC based on ONVIF",
#     "Model": "Bullet 7Q",
#     "SerialNumber": "111475266"
# }

# URL RTSP
rtsp_url = "rtsp://admin:admin@192.168.0.130:8554/Streaming/Channels/102" # HD
# rtsp_url = "rtsp://admin:admin@192.168.0.130:8554/Streaming/Channels/102" # SD
print(f"RTSP URL: {rtsp_url}")

# Mengakses stream video menggunakan OpenCV 
cap = cv2.VideoCapture(rtsp_url)

if not cap.isOpened():
    print("Error: Could not open video stream")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read frame")
        break

    # Tampilkan frame
    frame = cv2.resize(frame, (640, 480))
    cv2.imshow('ONVIF Camera', frame)

    # Tekan 'q' untuk keluar
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Melepaskan capture dan menutup jendela OpenCV
cap.release()
cv2.destroyAllWindows()
