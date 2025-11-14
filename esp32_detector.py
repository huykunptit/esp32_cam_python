import cv2
import numpy as np
import requests
from PIL import Image
import io
import time

class ESP32CamDetector:
    def __init__(self, esp32_ip="10.13.20.248"):
        """
        Khởi tạo detector cho ESP32-CAM
        
        Args:
            esp32_ip (str): IP address của ESP32-CAM
        """
        self.esp32_ip = esp32_ip
        self.stream_url = f"http://{esp32_ip}/capture"
        
        # Khởi tạo MobileNet SSD model cho nhận diện
        self.net = cv2.dnn.readNetFromCaffe(
            'MobileNetSSD_deploy.prototxt.txt',
            'MobileNetSSD_deploy.caffemodel'
        )
        
        # Danh sách các class có thể nhận diện
        self.classes = [
            'background', 'person', 'bicycle', 'car', 'motorcycle', 'airplane',
            'bus', 'train', 'truck', 'boat', 'traffic light', 'fire hydrant',
            'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse',
            'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
            'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis',
            'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
            'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass',
            'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
            'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
            'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed',
            'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
            'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
            'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
            'hair drier', 'toothbrush'
        ]
        
        # Màu sắc cho bounding box
        self.colors = np.random.uniform(0, 255, size=(len(self.classes), 3))
        
    def get_frame_from_esp32(self):
        """
        Lấy frame từ ESP32-CAM
        
        Returns:
            numpy.ndarray: Frame image hoặc None nếu lỗi
        """
        try:
            response = requests.get(self.stream_url, timeout=5)
            if response.status_code == 200:
                # Chuyển đổi bytes thành image
                image = Image.open(io.BytesIO(response.content))
                # Chuyển đổi PIL Image thành OpenCV format
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                return frame
            else:
                print(f"Lỗi kết nối ESP32-CAM: {response.status_code}")
                return None
        except Exception as e:
            print(f"Lỗi khi lấy frame: {e}")
            return None
    
    def detect_objects(self, frame):
        """
        Nhận diện objects trong frame
        
        Args:
            frame: Input frame
            
        Returns:
            tuple: (frame_with_detections, detections_info)
        """
        height, width = frame.shape[:2]
        
        # Chuẩn bị blob cho MobileNet SSD
        blob = cv2.dnn.blobFromImage(
            frame, 0.007843, (300, 300), 127.5
        )
        
        # Đưa blob vào network
        self.net.setInput(blob)
        detections = self.net.forward()
        
        detections_info = []
        
        # Xử lý kết quả detection
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            # Chỉ hiển thị detections với confidence > 0.5
            if confidence > 0.5:
                class_id = int(detections[0, 0, i, 1])
                
                # Tính toán bounding box
                x_left = int(detections[0, 0, i, 3] * width)
                y_top = int(detections[0, 0, i, 4] * height)
                x_right = int(detections[0, 0, i, 5] * width)
                y_bottom = int(detections[0, 0, i, 6] * height)
                
                # Vẽ bounding box
                color = self.colors[class_id]
                cv2.rectangle(frame, (x_left, y_top), (x_right, y_bottom), color, 2)
                
                # Vẽ label
                label = f"{self.classes[class_id]}: {confidence:.2f}"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                
                cv2.rectangle(
                    frame, 
                    (x_left, y_top - label_size[1] - 10),
                    (x_left + label_size[0], y_top),
                    color, -1
                )
                
                cv2.putText(
                    frame, label,
                    (x_left, y_top - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2
                )
                
                detections_info.append({
                    'class': self.classes[class_id],
                    'confidence': confidence,
                    'bbox': (x_left, y_top, x_right, y_bottom)
                })
        
        return frame, detections_info
    
    def run_detection(self):
        """
        Chạy detection loop chính
        """
        print("Bắt đầu nhận diện từ ESP32-CAM...")
        print("Nhấn 'q' để thoát")
        
        while True:
            # Lấy frame từ ESP32-CAM
            frame = self.get_frame_from_esp32()
            
            if frame is None:
                print("Không thể lấy frame từ ESP32-CAM")
                time.sleep(1)
                continue
            
            # Nhận diện objects
            frame_with_detections, detections = self.detect_objects(frame)
            
            # Hiển thị số lượng detections
            cv2.putText(
                frame_with_detections,
                f"Detections: {len(detections)}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
            )
            
            # Hiển thị frame
            cv2.imshow('ESP32-CAM Object Detection', frame_with_detections)
            
            # In thông tin detections
            if detections:
                print(f"\nDetections tại {time.strftime('%H:%M:%S')}:")
                for det in detections:
                    print(f"  - {det['class']}: {det['confidence']:.2f}")
            
            # Kiểm tra phím thoát
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()
        print("Đã thoát chương trình")

def download_model_files():
    """
    Tải xuống các file model cần thiết
    """
    import urllib.request
    
    print("Đang tải xuống MobileNet SSD model files...")
    
    # URLs cho MobileNet SSD files
    prototxt_url = "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/MobileNetSSD_deploy.prototxt"
    model_url = "https://github.com/chuanqi305/MobileNet-SSD/raw/master/MobileNetSSD_deploy.caffemodel"
    
    try:
        urllib.request.urlretrieve(prototxt_url, "MobileNetSSD_deploy.prototxt.txt")
        print("✓ Đã tải prototxt file")
        
        urllib.request.urlretrieve(model_url, "MobileNetSSD_deploy.caffemodel")
        print("✓ Đã tải model file")
        
        print("Hoàn thành tải xuống model files!")
        return True
    except Exception as e:
        print(f"Lỗi khi tải model files: {e}")
        return False

if __name__ == "__main__":
    # Kiểm tra và tải model files nếu cần
    import os
    
    if not os.path.exists("MobileNetSSD_deploy.prototxt.txt") or not os.path.exists("MobileNetSSD_deploy.caffemodel"):
        print("Model files chưa tồn tại. Đang tải xuống...")
        if not download_model_files():
            print("Không thể tải model files. Vui lòng kiểm tra kết nối internet.")
            exit(1)
    
    # Khởi tạo và chạy detector
    detector = ESP32CamDetector("10.13.20.248")
    detector.run_detection()
