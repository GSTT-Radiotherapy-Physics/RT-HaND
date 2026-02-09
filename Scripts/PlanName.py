import os
import zipfile
import pydicom
import pandas as pd
from io import BytesIO
import logging
from pathlib import Path
import argparse

# === Logging setup ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
# === Command-line arguments === 
parser = argparse.ArgumentParser(description="Extract RTPLAN dose & fractionation info from DICOM folders") 
parser.add_argument("base_dir", help="Path to folder containing patient subfolders with DICOMs") 
parser.add_argument("output_csv", help="Path to output CSV file") 
parser.add_argument("--use-name", action="store_true", help="Use PatientName instead of PatientID") 
args = parser.parse_args()

BASE_DIR = Path(args.base_dir)
OUTPUT_CSV = args.output_csv
USE_PATIENT_ID = not args.use_name

# === DICOM UID constants ===
RTPLAN_UID = '1.2.840.10008.5.1.4.1.1.481.5'  # RT Plan Storage

# === Helper to extract dose + fractionation ===
def extract_plan_info(ds):
    total_dose = None
    n_fracs    = None
    per_frac   = None

    # 1) look for TargetPrescriptionDose
    if hasattr(ds, "DoseReferenceSequence"):
        for dr in ds.DoseReferenceSequence:
            if getattr(dr, 'DoseReferenceType', '').upper() == 'TARGET':
                val = getattr(dr, 'TargetPrescriptionDose', None)
                if val is not None:
                    total_dose = float(val)
                    break

    # 2) always pull number of fractions
    if hasattr(ds, "FractionGroupSequence") and ds.FractionGroupSequence:
        fg = ds.FractionGroupSequence[0]
        if getattr(fg, "NumberOfFractionsPlanned", None) is not None:
            n_fracs = int(fg.NumberOfFractionsPlanned)
        if getattr(fg, "PlannedDoseValue", None) is not None:
            per_frac = float(fg.PlannedDoseValue)
        # compute total if missing
        if total_dose is None and per_frac is not None and n_fracs is not None:
            total_dose = per_frac * n_fracs

    return total_dose, n_fracs, per_frac

# === 1) Find all ZIPs under BASE_DIR ===
zip_paths = []
for root, _, files in os.walk(BASE_DIR):
    for f in files:
        if f.lower().endswith(".zip"):
            zip_paths.append(os.path.join(root, f))
logger.info(f"Found {len(zip_paths)} ZIP files to scan")

# === 2) Scan each ZIP for RTPLANs ===
rows = []
total_zips = len(zip_paths)
for zi_idx, zip_path in enumerate(zip_paths, start=1):
    logger.info(f"[{zi_idx}/{total_zips}] Scanning {os.path.basename(zip_path)}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            entries = zf.infolist()
            plan_count = 0
            for entry_idx, entry in enumerate(entries, start=1):
                if not entry.filename.lower().endswith(".dcm"):
                    continue
                with zf.open(entry) as fp:
                    ds = pydicom.dcmread(BytesIO(fp.read()), stop_before_pixels=True)
                if ds.SOPClassUID != RTPLAN_UID:
                    continue

                pid   = ds.PatientID.strip() if USE_PATIENT_ID else str(ds.get("PatientName","")).strip()
                plan  = str(ds.get("RTPlanLabel","")).strip()
                total_dose, n_fracs, per_frac = extract_plan_info(ds)

                # round to 1 d.p.
                if total_dose is not None:
                    total_dose = round(total_dose, 1)
                if per_frac is not None:
                    per_frac = round(per_frac, 1)

                rows.append((pid, plan, total_dose, n_fracs))
                plan_count += 1

                if entry_idx % 50 == 0:
                    logger.debug(f"processed {entry_idx}/{len(entries)} entries")

            logger.info(f"Extracted {plan_count} RTPLANs from this ZIP")
    except Exception as e:
        logger.error(f"Failed to open {zip_path}: {e}")

# === 3) Build DataFrame & dedupe ===
df = pd.DataFrame(rows, columns=[
    'Patient', 'PlanLabel', 'TotalDoseGy', 'NumFractions'
]).drop_duplicates()

# correct missing DosePerFractionGy = TotalDoseGy/NumFractions
df['DosePerFractionGy'] = df.apply(
    lambda r: round(r.TotalDoseGy / r.NumFractions, 1)
    if pd.notna(r.TotalDoseGy) and pd.notna(r.NumFractions) else None,
    axis=1
)

# === 4) Group & expand to wide ===
grouped = df.groupby('Patient').agg(list)
max_plans = grouped['PlanLabel'].map(len).max()

wide_records = []
for patient, row in grouped.iterrows():
    rec = {'Patient': patient}
    for i in range(max_plans):
        rec[f'Plan{i+1}']        = row['PlanLabel'][i]        if i < len(row['PlanLabel']) else ''
        rec[f'TotalDose{i+1}']   = row['TotalDoseGy'][i]      if i < len(row['TotalDoseGy']) else ''
        rec[f'NumFracs{i+1}']    = row['NumFractions'][i]     if i < len(row['NumFractions']) else ''
    wide_records.append(rec)

wide_df = pd.DataFrame(wide_records)
# reorder cols
cols = ['Patient'] + sum([[f'Plan{i+1}', f'TotalDose{i+1}', f'NumFracs{i+1}']
                         for i in range(max_plans)], [])
wide_df = wide_df[cols]

# === 5) Save CSV ===
wide_df.to_csv(OUTPUT_CSV, index=False)
logger.info(f" Wrote {len(wide_df)} patientsup to {max_plans} plans {OUTPUT_CSV}")