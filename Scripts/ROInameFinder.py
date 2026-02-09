import os
import zipfile
import pydicom
import pandas as pd
from io import BytesIO
import logging

# === Logging setup ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# === User inputs ===
BASE_DIR = "HeadNodeBatch9"  # folder containing many .zip subfolders/files
OUTPUT_CSV = "HeadNodeBatch9/structures_list.csv"
OUTPUT_PER_SET_CSV="HeadNodeBatch9/batch_9.csv"
OUTPUT_GLOBAL_CSV="HeadNodeBatch9/ROIs.csv"
USE_PATIENT_ID = True  # if False, uses PatientName


# Containers
per_set_records = []
global_rois = set()

# Single pass: scan each ZIP once
for root, _, files in os.walk(BASE_DIR):
    for fname in files:
        if not fname.lower().endswith(".zip"):
            continue

        zip_path = os.path.join(root, fname)
        logger.info(f"→ Scanning ZIP: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            for entry in zf.namelist():
                try:
                    data = zf.read(entry)
                    ds = pydicom.dcmread(BytesIO(data), stop_before_pixels=True, force=True)
                except Exception:
                    continue

                if getattr(ds, "Modality", "").upper() != "RTSTRUCT":
                    continue

                # Extract IDs and label
                patient_id = ds.PatientID if USE_PATIENT_ID and "PatientID" in ds else ds.get("PatientName", "UNKNOWN")
                set_label = getattr(ds, "StructureSetLabel", "NO_LABEL")

                # Collect ROI names
                roi_names = sorted({roi.ROIName for roi in getattr(ds, "StructureSetROISequence", [])})
                # Add to per-set records
                per_set_records.append({
                    "PatientID": str(patient_id),
                    "StructureSetLabel": set_label,
                    "ROI_Count": len(roi_names),
                    "UniqueROIList": ";".join(roi_names)
                })
                # Add to global set
                global_rois.update(roi_names)

# Write per-set CSV
df_per_set = pd.DataFrame(per_set_records)
df_per_set.to_csv(OUTPUT_PER_SET_CSV, index=False)
logger.info(f"✅ Per-set CSV written: {OUTPUT_PER_SET_CSV} ({len(per_set_records)} rows)")

# Write global unique ROI list CSV
df_global = pd.DataFrame([{"UniqueROIList": ";".join(sorted(global_rois))}])
df_global.to_csv(OUTPUT_GLOBAL_CSV, index=False)
logger.info(f"✅ Global unique ROIs CSV written: {OUTPUT_GLOBAL_CSV} ({len(global_rois)} ROIs)")