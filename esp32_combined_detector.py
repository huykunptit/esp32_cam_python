import cv2
import numpy as np
import requests
from PIL import Image
import io
import time
from collections import defaultdict, deque

class ESP32CamCombinedDetector:
    def __init__(self, esp32_ip="192.168.0.109"):
        """
        Detector kết hợp người và đồ vật cho ESP32-CAM
        
        Args:
            esp32_ip (str): IP address của ESP32-CAM
        """
        self.esp32_ip = esp32_ip
        self.stream_url = f"http://{esp32_ip}/capture"
        
        # Khởi tạo cascade cho người
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
        
        # Cascade cho người
        self.person_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_fullbody.xml')
        if self.person_cascade.empty():
            self.person_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')
        
        # Cascade cho đồ vật (loại bỏ smile vì quá nhạy)
        self.object_cascades = {}
        object_info = {
            'car': ('haarcascade_car.xml', (0, 255, 0)),
            'eye': ('haarcascade_eye.xml', (255, 0, 0)),
            'watch': ('haarcascade_watch.xml', (255, 0, 255)),
            'clock': ('haarcascade_clock.xml', (255, 255, 0))
        }
        
        for obj_name, (cascade_file, color) in object_info.items():
            cascade_path = cv2.data.haarcascades + cascade_file
            cascade = cv2.CascadeClassifier(cascade_path)
            if not cascade.empty():
                self.object_cascades[obj_name] = (cascade, color)
        
        # Buffer để smoothing
        self.face_buffer = deque(maxlen=3)
        self.people_buffer = deque(maxlen=3)
        self.object_buffer = deque(maxlen=3)
        
        # Thống kê
        self.stats = {
            'faces': 0,
            'people': 0,
            'objects': defaultdict(int),
            'total_frames': 0
        }
        
        print(f"Kết nối ESP32-CAM tại: {self.stream_url}")
        print(f"✓ Đã tải {len(self.object_cascades)} cascade(s) cho đồ vật (đã loại bỏ smile cascade)")
        
    def get_frame_from_esp32(self):
        """Lấy frame từ ESP32-CAM"""
        try:
            response = requests.get(self.stream_url, timeout=2)
            if response.status_code == 200:
                image = Image.open(io.BytesIO(response.content))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                # Resize để tối ưu
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_width = 640
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                return frame
            else:
                return None
        except Exception as e:
            return None
    
    def detect_people(self, frame):
        """Nhận diện người và mặt"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Nhận diện mặt
        faces_frontal = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=3, minSize=(20, 20)
        )
        
        faces_profile = self.profile_cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=3, minSize=(20, 20)
        )
        
        # Kết hợp faces
        all_faces = []
        for (x, y, w, h) in faces_frontal:
            all_faces.append((x, y, w, h))
        for (x, y, w, h) in faces_profile:
            all_faces.append((x, y, w, h))
        
        # Loại bỏ trùng lặp
        filtered_faces = self._remove_overlapping_detections(all_faces)
        
        # Nhận diện người
        people = []
        if not self.person_cascade.empty():
            people = self.person_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=3, minSize=(40, 40)
            )
            people = self._remove_overlapping_detections(people)
        
        # Logic thông minh: ước tính người từ mặt
        estimated_people = len(people)
        if len(filtered_faces) > 0 and len(people) == 0:
            estimated_people = len(filtered_faces)
        
        # Vẽ bounding boxes
        for i, (x, y, w, h) in enumerate(filtered_faces):
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.putText(frame, f'Face {i+1}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        for i, (x, y, w, h) in enumerate(people):
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, f'Person {i+1}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return len(filtered_faces), estimated_people
    
    def detect_objects(self, frame):
        """Nhận diện đồ vật"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        object_counts = defaultdict(int)
        
        for obj_name, (cascade, color) in self.object_cascades.items():
            objects = cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20)
            )
            
            for i, (x, y, w, h) in enumerate(objects):
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(frame, f'{obj_name.title()} {i+1}', 
                           (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                object_counts[obj_name] += 1
        
        return dict(object_counts)
    
    def _remove_overlapping_detections(self, detections, threshold=0.3):
        """Loại bỏ detections trùng lặp"""
        if len(detections) <= 1:
            return detections
        
        filtered = []
        for i, det1 in enumerate(detections):
            x1, y1, w1, h1 = det1
            is_duplicate = False
            
            for j, det2 in enumerate(detections):
                if i == j:
                    continue
                    
                x2, y2, w2, h2 = det2
                
                # Tính IoU
                x_left = max(x1, x2)
                y_top = max(y1, y2)
                x_right = min(x1 + w1, x2 + w2)
                y_bottom = min(y1 + h1, y2 + h2)
                
                if x_right < x_left or y_bottom < y_top:
                    continue
                
                intersection = (x_right - x_left) * (y_bottom - y_top)
                area1 = w1 * h1
                area2 = w2 * h2
                union = area1 + area2 - intersection
                
                if union > 0:
                    iou = intersection / union
                    if iou > threshold:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                filtered.append(det1)
        
        return filtered
    
    def run_detection(self):
        """Chạy detection loop chính"""
        print("🚀 Bắt đầu nhận diện kết hợp từ ESP32-CAM...")
        print("📋 Điều khiển:")
        print("   - 'q': Thoát")
        print("   - 's': Chụp ảnh")
        print("   - 'r': Reset thống kê")
        print("   - 't': Chuyển đổi hiển thị")
        
        fps_counter = 0
        fps_start_time = time.time()
        last_print_time = time.time()
        show_detailed = True
        
        while True:
            current_time = time.time()
            
            # Lấy frame
            frame = self.get_frame_from_esp32()
            
            if frame is None:
                time.sleep(0.1)
                continue
            
            # Nhận diện người
            face_count, people_count = self.detect_people(frame)
            
            # Nhận diện đồ vật
            object_counts = self.detect_objects(frame)
            
            # Cập nhật buffer
            self.face_buffer.append(face_count)
            self.people_buffer.append(people_count)
            self.object_buffer.append(sum(object_counts.values()))
            
            # Smoothing
            smoothed_faces = int(np.mean(self.face_buffer))
            smoothed_people = int(np.mean(self.people_buffer))
            smoothed_objects = int(np.mean(self.object_buffer))
            
            # Tính FPS
            fps_counter += 1
            if fps_counter % 30 == 0:
                fps = fps_counter / (current_time - fps_start_time)
                fps_counter = 0
                fps_start_time = current_time
            else:
                fps = 0
            
            # Hiển thị thông tin
            cv2.putText(frame, f"Faces: {smoothed_faces}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            cv2.putText(frame, f"People: {smoothed_people}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Objects: {smoothed_objects}", (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            if fps > 0:
                cv2.putText(frame, f"FPS: {fps:.1f}", (10, 120), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Hiển thị chi tiết đồ vật
            if show_detailed and object_counts:
                y_offset = 150
                for obj_name, count in sorted(object_counts.items(), key=lambda x: x[1], reverse=True):
                    cv2.putText(frame, f"{obj_name.title()}: {count}", 
                               (10, y_offset), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    y_offset += 20
            
            cv2.putText(frame, f"ESP32: {self.esp32_ip}", 
                       (10, frame.shape[0] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Hiển thị frame
            cv2.imshow('ESP32-CAM Combined Detection', frame)
            
            # Cập nhật thống kê
            self.stats['faces'] += smoothed_faces
            self.stats['people'] += smoothed_people
            self.stats['total_frames'] += 1
            
            for obj_name, count in object_counts.items():
                self.stats['objects'][obj_name] += count
            
            # In thông tin định kỳ
            if current_time - last_print_time > 5:
                print(f"📊 Detections: Faces={smoothed_faces}, People={smoothed_people}, Objects={smoothed_objects}")
                if object_counts:
                    print(f"   Objects: {dict(list(sorted(object_counts.items(), key=lambda x: x[1], reverse=True))[:3])}")
                last_print_time = current_time
            
            # Xử lý phím
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                filename = f"esp32_combined_{int(time.time())}.jpg"
                cv2.imwrite(filename, frame)
                print(f"📸 Đã chụp ảnh: {filename}")
            elif key == ord('r'):
                self.stats = {'faces': 0, 'people': 0, 'objects': defaultdict(int), 'total_frames': 0}
                print("🔄 Đã reset thống kê")
            elif key == ord('t'):
                show_detailed = not show_detailed
                print(f"🔄 Hiển thị chi tiết: {'Bật' if show_detailed else 'Tắt'}")
        
        cv2.destroyAllWindows()
        self._print_final_stats()
    
    def _print_final_stats(self):
        """In thống kê cuối"""
        print("\n📊 Thống kê cuối:")
        print(f"   - Tổng frames: {self.stats['total_frames']}")
        print(f"   - Tổng faces: {self.stats['faces']}")
        print(f"   - Tổng people: {self.stats['people']}")
        print(f"   - Tổng objects: {sum(self.stats['objects'].values())}")
        
        if self.stats['objects']:
            print("   - Top objects:")
            sorted_objects = sorted(self.stats['objects'].items(), key=lambda x: x[1], reverse=True)
            for obj_name, count in sorted_objects[:5]:
                print(f"     {obj_name.title()}: {count}")

if __name__ == "__main__":
    detector = ESP32CamCombinedDetector("192.168.0.109")
    detector.run_detection()
