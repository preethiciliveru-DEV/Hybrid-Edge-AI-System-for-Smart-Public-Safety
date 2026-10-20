"""
Colab-ready training script for YOLOv8 baseline.

Usage in Google Colab:
1. Upload this file to Colab or paste its contents into a new notebook cell.
2. Mount Google Drive if you want to save weights: from google.colab import drive; drive.mount('/content/drive')
3. Install dependencies: !pip install ultralytics roboflow opencv-python
4. If using Roboflow-hosted dataset, set ROBOFLOW_API_KEY and PROJECT_ID and download dataset export via Roboflow Python SDK or REST API.
5. Run the training cells below. Adjust parameters as needed.

This script contains utility functions and an example training command. It does NOT run automatically as a single script in Colab — paste cells into a Colab notebook for interactive use.
"""

# Cell 1: install dependencies
print('Run in Colab cell:')
print('!pip install ultralytics roboflow opencv-python')

# Cell 2: optional - download dataset from Roboflow (requires api key and project/version)
print('\nExample to download a YOLO export from Roboflow (replace placeholders):')
print("""
from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_ROBOFLOW_API_KEY")
project = rf.workspace().project("preethies/hybridsafety-weapons")
# List versions
for v in project.versions().get('versions', []):
    print(v)
# Download a YOLOv8 export for a version (replace '1' with your version id):
project.version(1).download("yolov8")  # will create a folder with yolov8 dataset
""")

# Cell 3: train with ultralytics (example)
print('\nAfter dataset is available as a folder with data.yaml, run:')
print("""
from ultralytics import YOLO
# Replace 'path/to/data.yaml' with actual path in Colab runtime
model = YOLO('yolov8n.pt')  # or start from pre-trained small model
model.train(data='path/to/data.yaml', epochs=100, imgsz=640, batch=16, lr0=0.01)
""")

# Cell 4: evaluate and export
print('\nAfter training, export weights and evaluate:')
print("""
# Evaluate
metrics = model.val()
print(metrics)
# Save best weights (Ultralytics saves in runs/train/expX/weights/best.pt)
# Download or copy to Drive
""")

print('\nNote: Labeling must be completed before training. Use Roboflow web UI or labelImg to create YOLO labels. For speed and high precision, upload labeled dataset to Roboflow and run RF-DETR there, which often gives better precision for weapon detection tasks.')
