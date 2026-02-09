from __future__ import annotations
import os
import zipfile
from io import BytesIO
import logging
import shutil
from collections import defaultdict
from datetime import datetime, timedelta

import pydicom
import pandas as pd
from pydicom.tag import Tag
from pathlib import Path
# =============================
# Configuration
# =============================
BASE_DIR = "HeadNodeBatch13"
#BASE_DIR = r"CLEA/test"
CSV_DIR = "csv"
WIDE_PLAN_CSV = os.path.join(CSV_DIR, "plan_info_wide.csv")
ID_MAPPING_CSV = os.path.join(CSV_DIR, "mapping.csv")
ROI_MAPPING_CSV = os.path.join(CSV_DIR, "roi_mapping.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "for_upload_CT_SS2")
SUMMARY_CSV = os.path.join(CSV_DIR, "summary_ct_ss.csv")
FILES_CSV = os.path.join(CSV_DIR, "files_ct_ss.csv")
ROI_LOG_CSV = os.path.join(CSV_DIR, "roi_anonymised_log.csv")
ROI_PATIENT_CSV = os.path.join(CSV_DIR, "roi_kept_by_patient_batchHeadNode1.csv")
CT_KEYS_CSV = os.path.join(CSV_DIR, "ct_keys_seen.csv")

USE_PATIENT_ID = True  # else use PatientName when matching plans
CLEAN_STAGING = True  # remove staging after processing
INDEX_ANY_CT = True  # index ALL CT (Enhanced or classic)

# Anon policy knobs (NO UID CHANGES HERE)
SHIFT_DAYS = 10  # shift dates by +10 days
ZERO_ALL_TIMES = True  # set all times to midnight
APPLY_POLICY_TO_RTSTRUCT = True
ANONYMIZE_PATIENT_ID = True

# ROI filtering knobs
ALLOW_ROI_FILTER = True
RENAMING_ONLY = False  # if True: rename only, do not drop unknown
RENUMBER_ROI = True  # renumber kept ROIs 1..N
REQUIRE_CT_BACKED_CONTOURS = True  # keep an ROI only if at least one contour references a CT we export

# SOP Class UIDs
UID_RTPLAN = '1.2.840.10008.5.1.4.1.1.481.5'
UID_RTSTRUCT = '1.2.840.10008.5.1.4.1.1.481.3'
UID_CT_IMAGE = '1.2.840.10008.5.1.4.1.1.2'

# Never delete these (critical references)
CRITICAL_REF_TAGS = {
    Tag(0x0008, 0x1110),  # ReferencedStudySequence
    Tag(0x0008, 0x1115),  # ReferencedSeriesSequence
    Tag(0x0008, 0x1140),  # ReferencedImageSequence
    Tag(0x0008, 0x1150),  # ReferencedSOPClassUID
    Tag(0x0008, 0x1155),  # ReferencedSOPInstanceUID
    Tag(0x3006, 0x0010),  # ReferencedFrameOfReferenceSequence
    Tag(0x3006, 0x0012),  # RTReferencedStudySequence
    Tag(0x3006, 0x0014),  # RTReferencedSeriesSequence
    Tag(0x3006, 0x0016),  # ContourImageSequence
    Tag(0x3006, 0x0039),  # ROIContourSequence
}

# =============================
# Logging
# =============================
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger('ctss_pipeline_no_uid_edits')


# =============================
# Helpers: ID mapping & wide plan parsing
# =============================

def read_id_mapping(path: str) -> dict:
    df = pd.read_csv(path, dtype=str).fillna("")
    if df.shape[1] < 3:
        raise ValueError("ID mapping CSV must have ≥3 columns: two original ID columns then anonymised ID column.")
    orig_cols = df.columns[:2].tolist()
    anon_col = df.columns[2]
    m = {}
    for _, r in df.iterrows():
        anon = r[anon_col].strip()
        for c in orig_cols:
            k = r[c].strip()
            if k:
                m[k] = anon
    logger.info(f"Loaded {len(m)} patient→anon mappings")
    return m


def load_plan_info(wide_csv: str) -> dict:
    """Parse the wide plan CSV and return {(patient, plan_label): {total, num_fracs, dose_per}}."""
    df = pd.read_csv(wide_csv, dtype=str).fillna("")
    info = {}
    if df.empty:
        logger.warning("Wide plan CSV is empty")
        return info
    patient_col = df.columns[0]
    plan_cols = [c for c in df.columns if c.lower().startswith('plan')]
    # discover matching dose/frac/per columns by numeric suffix
    dose_cols = {}
    frac_cols = {}
    per_cols = {}
    for c in df.columns:
        lc = c.lower()
        for i in range(1, len(plan_cols) + 1):
            if lc.endswith(str(i)):
                if 'dose' in lc and 'per' not in lc:
                    dose_cols[i] = c
                if 'frac' in lc and 'dose' not in lc:
                    frac_cols[i] = c
                if 'doseper' in lc or ('dose' in lc and 'per' in lc):
                    per_cols[i] = c
    for _, r in df.iterrows():
        pid = r[patient_col].strip()
        for i, pcol in enumerate(plan_cols, start=1):
            plan = r[pcol].strip()
            if not plan:
                continue
            td = None;
            nf = None;
            pf = None
            if i in dose_cols and r[dose_cols[i]].strip():
                try:
                    td = float(r[dose_cols[i]].strip())
                except:
                    pass
            if i in frac_cols and r[frac_cols[i]].strip():
                try:
                    nf = int(float(r[frac_cols[i]].strip()))
                except:
                    pass
            if i in per_cols and r[per_cols[i]].strip():
                try:
                    pf = float(r[per_cols[i]].strip())
                except:
                    pass
            if pf is None and td is not None and nf:
                pf = td / nf
            info[(pid, plan)] = {'total': td, 'num_fracs': nf, 'dose_per': pf}
    logger.info(f"Parsed {len(info)} kept (patient, plan) entries from wide CSV")
    return info


# =============================
# Helpers: ROI mapping & RTSTRUCT filtering
# =============================

def read_roi_mapping(path: str) -> dict:
    """Read ROI mapping CSV. Returns dict of lowercased source -> canonical name."""
    df = pd.read_csv(path, dtype=str).fillna("")
    if df.shape[1] < 2:
        raise ValueError("ROI mapping CSV must have at least 2 columns.")
    src_to_canon = {}
    cols = df.columns.tolist()
    for _, row in df.iterrows():
        canon = row[cols[-1]].strip()
        if not canon:
            continue
        sources = [row[cols[0]].strip()] if df.shape[1] == 2 else [row[c].strip() for c in cols[:-1] if row[c].strip()]
        for s in sources:
            key = s.strip().lower()
            if key:
                src_to_canon[key] = canon
    logger.info(f"Loaded {len(src_to_canon)} ROI source→canonical mappings")
    return src_to_canon

def append_roi_kept_rows(path: str, rows: list):
    if not rows:
        return
    df = pd.DataFrame(rows)
    header = not os.path.exists(path)
    df.to_csv(path, mode='a', header=header, index=False)

def harmonise_and_filter_rtstruct(
        ds: pydicom.dataset.FileDataset,
        src2canon: dict,
        renumber: bool = True,
        drop_unknown: bool = True,
        ct_uid_set=None,
):
    """
    Keep/rename/renumber RTSTRUCT ROIs based on src2canon mapping.
    If ct_uid_set and REQUIRE_CT_BACKED_CONTOURS are True, require at least one contour referencing a CT in ct_uid_set.
    Returns: (kept_count, dropped_count, kept_detail:list[dict], dropped_names:list[str])

    Safety: if result would leave SSROI>0 but ROIContourSequence empty, returns kept=0 so caller can revert.
    """
    ss_seq = list(getattr(ds, 'StructureSetROISequence', []) or [])
    rc_seq = list(getattr(ds, 'ROIContourSequence', []) or [])
    ro_seq = list(getattr(ds, 'RTROIObservationsSequence', []) or [])

    if not ss_seq:
        return (0, 0, [], [])

    # current names
    old_names = {int(it.ROINumber): str(getattr(it, 'ROIName', '')).strip() for it in ss_seq}

    # decide keep set
    keep_nums = set()
    for rn, nm in old_names.items():
        if nm and nm.lower() in src2canon:
            keep_nums.add(rn)
    if not drop_unknown:
        keep_nums = set(old_names.keys())

    if drop_unknown and not keep_nums:
        return (0, len(old_names), [], sorted(old_names.values()))

    # require CT-backed contours?
    if REQUIRE_CT_BACKED_CONTOURS and ct_uid_set and rc_seq:
        backed = set()
        for roi in rc_seq:
            rn = int(getattr(roi, 'ReferencedROINumber', 0) or 0)
            if rn not in keep_nums:
                continue
            for ct in getattr(roi, 'ContourSequence', []) or []:
                ok = False
                for ref in getattr(ct, 'ContourImageSequence', []) or []:
                    uid = str(getattr(ref, 'ReferencedSOPInstanceUID', '')).strip()
                    if uid and uid in ct_uid_set:
                        ok = True
                        break
                if ok:
                    backed.add(rn)
                    break
        if drop_unknown:
            keep_nums &= backed
            if not keep_nums:
                return (0, len(old_names), [], sorted(old_names.values()))

    # new SSROI
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-(). ")

    def _safe(n):
        return ''.join(ch if ch in allowed else '_' for ch in (n or '').strip())

    old2new, kept_detail, new_ss = {}, [], []
    next_num = 1
    for it in ss_seq:
        rn = int(it.ROINumber)
        if rn not in keep_nums:
            continue
        old = old_names[rn]
        new = src2canon.get(old.lower(), old)
        ns = _safe(new)
        it.ROIName = ns
        if renumber:
            old2new[rn] = next_num
            it.ROINumber = next_num
            kept_detail.append({'old_name': old, 'new_name': ns, 'old_number': rn, 'new_number': next_num})
            next_num += 1
        else:
            old2new[rn] = rn
            kept_detail.append({'old_name': old, 'new_name': ns, 'old_number': rn, 'new_number': rn})
        new_ss.append(it)
    ds.StructureSetROISequence = new_ss

    # rebuild ROIContourSequence
    if rc_seq:
        new_rc = []
        for roi in rc_seq:
            rn = int(getattr(roi, 'ReferencedROINumber', 0) or 0)
            if rn not in keep_nums:
                continue
            roi.ReferencedROINumber = old2new.get(rn, rn)
            if REQUIRE_CT_BACKED_CONTOURS and ct_uid_set:
                new_cts = []
                for ct in getattr(roi, 'ContourSequence', []) or []:
                    imgs = getattr(ct, 'ContourImageSequence', []) or []
                    kept_imgs = [ref for ref in imgs if
                                 str(getattr(ref, 'ReferencedSOPInstanceUID', '')).strip() in ct_uid_set]
                    if kept_imgs:
                        ct.ContourImageSequence = kept_imgs
                        new_cts.append(ct)
                roi.ContourSequence = new_cts
                if not new_cts:
                    continue
            new_rc.append(roi)
        ds.ROIContourSequence = new_rc

    # rebuild RTROIObservationsSequence
    if ro_seq:
        new_ro = []
        for ob in ro_seq:
            rn = int(getattr(ob, 'ReferencedROINumber', 0) or 0)
            if rn not in keep_nums:
                continue
            ob.ReferencedROINumber = old2new.get(rn, rn)
            new_ro.append(ob)
        ds.RTROIObservationsSequence = new_ro

    # safety: SSROI>0 but empty ROIContourSequence -> tell caller to revert
    if ds.StructureSetROISequence and (
            getattr(ds, 'ROIContourSequence', None) is None or len(ds.ROIContourSequence) == 0):
        return (0, len(old_names), [], sorted(old_names.values()))

    kept_count = len(ds.StructureSetROISequence)
    dropped_names = [old_names[rn] for rn in sorted(old_names) if rn not in keep_nums]
    return (kept_count, len(dropped_names), kept_detail, dropped_names)


# =============================
# XNAT-style anonymisation (NO UID CHANGES)
# =============================

DELETE_TAGS = {
    # dates/times & loads of PHI; we’ll subtract critical ref tags below
    Tag(0x0008, 0x0012), Tag(0x0008, 0x0013), Tag(0x0008, 0x002A),
    Tag(0x0008, 0x0024), Tag(0x0008, 0x0025), Tag(0x0008, 0x0031), Tag(0x0008, 0x0032),
    Tag(0x0008, 0x0034), Tag(0x0008, 0x0035), Tag(0x0008, 0x0080), Tag(0x0008, 0x0081), Tag(0x0008, 0x0082),
    Tag(0x0008, 0x0092), Tag(0x0008, 0x0094), Tag(0x0008, 0x0096), Tag(0x0008, 0x0201), Tag(0x0008, 0x1010),
    Tag(0x0008, 0x1048), Tag(0x0008, 0x1049), Tag(0x0008, 0x1050), Tag(0x0008, 0x1052), Tag(0x0008, 0x1060),
    Tag(0x0008, 0x1062), Tag(0x0008, 0x1070), Tag(0x0008, 0x1072), Tag(0x0008, 0x1080), Tag(0x0008, 0x1084),
    Tag(0x0008, 0x1111), Tag(0x0008, 0x1120), Tag(0x0008, 0x2111), Tag(0x0008, 0x2112), Tag(0x0008, 0x4000),
    Tag(0x0010, 0x0021), Tag(0x0010, 0x0032), Tag(0x0010, 0x0050), Tag(0x0010, 0x0101), Tag(0x0010, 0x0102),
    Tag(0x0010, 0x1000), Tag(0x0010, 0x1001), Tag(0x0010, 0x1002), Tag(0x0010, 0x1005), Tag(0x0010, 0x1040),
    Tag(0x0010, 0x1050), Tag(0x0010, 0x1060), Tag(0x0010, 0x1080), Tag(0x0010, 0x1081), Tag(0x0010, 0x1090),
    Tag(0x0010, 0x2000), Tag(0x0010, 0x2110), Tag(0x0010, 0x2150), Tag(0x0010, 0x2152), Tag(0x0010, 0x2154),
    Tag(0x0010, 0x2180), Tag(0x0010, 0x21B0), Tag(0x0010, 0x21D0), Tag(0x0010, 0x21F0), Tag(0x0010, 0x2297),
    Tag(0x0010, 0x2299), Tag(0x0010, 0x4000),
    Tag(0x0032, 0x0012), Tag(0x0032, 0x1020), Tag(0x0032, 0x1021), Tag(0x0032, 0x1030), Tag(0x0032, 0x1032),
    Tag(0x0032, 0x1033),
    Tag(0x0032, 0x1060), Tag(0x0032, 0x1070), Tag(0x0032, 0x4000),
    Tag(0x0038, 0x0010), Tag(0x0038, 0x0011), Tag(0x0038, 0x001E), Tag(0x0038, 0x0020), Tag(0x0038, 0x0021),
    Tag(0x0038, 0x0040),
    Tag(0x0038, 0x0050), Tag(0x0038, 0x0060), Tag(0x0038, 0x0061), Tag(0x0038, 0x0062), Tag(0x0038, 0x0300),
    Tag(0x0038, 0x0400),
    Tag(0x0038, 0x0500), Tag(0x0038, 0x1234), Tag(0x0038, 0x4000),
    Tag(0x0040, 0x0001), Tag(0x0040, 0x0002), Tag(0x0040, 0x0003), Tag(0x0040, 0x0004), Tag(0x0040, 0x0005),
    Tag(0x0040, 0x0006),
    Tag(0x0040, 0x0007), Tag(0x0040, 0x000B), Tag(0x0040, 0x0010), Tag(0x0040, 0x0011), Tag(0x0040, 0x0012),
    Tag(0x0040, 0x0241), Tag(0x0040, 0x0242), Tag(0x0040, 0x0243), Tag(0x0040, 0x0244), Tag(0x0040, 0x0245),
    Tag(0x0040, 0x0248),
    Tag(0x0040, 0x0253), Tag(0x0040, 0x0254), Tag(0x0040, 0x0275), Tag(0x0040, 0x0280), Tag(0x0040, 0x0555),
    Tag(0x0040, 0x1004),
    Tag(0x0040, 0x1005), Tag(0x0040, 0x1010), Tag(0x0040, 0x1011), Tag(0x0040, 0x1102), Tag(0x0040, 0x1103),
    Tag(0x0040, 0x1400),
    Tag(0x0040, 0x2001), Tag(0x0040, 0x2008), Tag(0x0040, 0x2009), Tag(0x0040, 0x2010), Tag(0x0040, 0x2400),
    Tag(0x0040, 0x3001),
    Tag(0x0040, 0x4025), Tag(0x0040, 0x4027), Tag(0x0040, 0x4030), Tag(0x0040, 0x4034), Tag(0x0040, 0x4035),
    Tag(0x0040, 0x4036),
    Tag(0x0040, 0x4037), Tag(0x0040, 0xA027), Tag(0x0040, 0xA078), Tag(0x0040, 0xA07A), Tag(0x0040, 0xA07C),
    Tag(0x0040, 0xA730),
    Tag(0x0040, 0xA123),
    Tag(0x2030, 0x0020), Tag(0x300E, 0x0008), Tag(0x4000, 0x0010), Tag(0x4000, 0x4000),
}

DATE_TAGS_HINT = {Tag(0x0008, 0x0020), Tag(0x0008, 0x0021), Tag(0x0008, 0x0022), Tag(0x0008, 0x0023),
                  Tag(0x0040, 0x0244), Tag(0x3006, 0x0008),  Tag(0x300E, 0x0004), Tag(0x3006, 0x0008), Tag(0x300E, 0x0004),}
TIME_TAGS_HINT = {Tag(0x0008, 0x0030), Tag(0x0008, 0x0031), Tag(0x0008, 0x0032), Tag(0x0008, 0x0033),
                  Tag(0x0040, 0x0245), Tag(0x3006, 0x0009), Tag(0x300E, 0x0005)}


def is_date_vr(elem) -> bool:
    return elem.VR in ('DA', 'DT') or elem.tag in DATE_TAGS_HINT


def is_time_vr(elem) -> bool:
    return elem.VR == 'TM' or elem.tag in TIME_TAGS_HINT


def shift_da(s: str, days: int) -> str:
    try:
        dt = datetime.strptime(s[:8], '%Y%m%d') + timedelta(days=days)
        return dt.strftime('%Y%m%d')
    except Exception:
        return s


def shift_dt(s: str, days: int, zero_time: bool) -> str:
    try:
        base = s
        yyyy = base[0:4];
        mm = base[4:6] or '01';
        dd = base[6:8] or '01'
        hh = '00' if zero_time else (base[8:10] or '00')
        mi = '00' if zero_time else (base[10:12] or '00')
        ss = '00' if zero_time else (base[12:14] or '00')
        fmt = f"{yyyy}{mm}{dd}{hh}{mi}{ss}"
        dt = datetime.strptime(fmt, '%Y%m%d%H%M%S') + timedelta(days=days)
        return dt.strftime('%Y%m%d%H%M%S')
    except Exception:
        return s


def apply_xnat_policy(ds: pydicom.dataset.Dataset):
    """Apply anonymisation WITHOUT touching any UID values or reference sequences."""
    # Always remove DOB/BirthTime/Reviewer
    for tg in (Tag(0x0010, 0x0030), Tag(0x0010, 0x0032), Tag(0x300E, 0x0008)):
        if tg in ds:
            try:
                ds.pop(tg)
            except Exception:
                pass

    # Delete lots of PHI tags but NEVER the critical ref tags
    delset = set(DELETE_TAGS) - CRITICAL_REF_TAGS
    for tg in list(delset):
        if tg in ds:
            try:
                ds.pop(tg)
            except Exception:
                pass

    # Shift dates & zero times recursively (keep UIDs intact)
    def recurse(elem_or_ds):
        if isinstance(elem_or_ds, pydicom.dataset.Dataset):
            for elem in list(elem_or_ds):
                if elem.VR == 'SQ':
                    for item in elem.value:
                        recurse(item)
                    continue
                if is_date_vr(elem):
                    try:
                        if elem.VR == 'DA' or elem.tag in DATE_TAGS_HINT:
                            if isinstance(elem.value, str):
                                elem.value = shift_da(elem.value, SHIFT_DAYS)
                        elif elem.VR == 'DT':
                            if isinstance(elem.value, str):
                                elem.value = shift_dt(elem.value, SHIFT_DAYS, ZERO_ALL_TIMES)
                    except Exception:
                        pass
                if ZERO_ALL_TIMES and is_time_vr(elem):
                    try:
                        if isinstance(elem.value, str):
                            elem.value = '000000'
                    except Exception:
                        pass

    recurse(ds)
    '''
        #try:
        #if Tag(0x3006, 0x0008) in ds:  # Structure Set Date
           # ds[Tag(0x3006, 0x0008)].value = shift_da(str(ds[Tag(0x3006, 0x0008)].value), SHIFT_DAYS)
       # if Tag(0x300E, 0x0004) in ds:  # Review Date
         #   ds[Tag(0x300E, 0x0004)].value = shift_da(str(ds[Tag(0x300E, 0x0004)].value), SHIFT_DAYS)

        # If you also want the times zeroed explicitly (already done by recurse if ZERO_ALL_TIMES):
        #if ZERO_ALL_TIMES:
            #if Tag(0x3006, 0x0009) in ds:  # Structure Set Time
             #   ds[Tag(0x3006, 0x0009)].value = '000000'
            #if Tag(0x300E, 0x0005) in ds:  # Review Time
              #  ds[Tag(0x300E, 0x0005)].value = '000000'
    #except Exception:
        #pass
'''
# =============================
# File meta hygiene
# =============================
from pydicom.dataset import FileMetaDataset


def ensure_file_meta(ds: pydicom.dataset.FileDataset):
    if not hasattr(ds, 'file_meta') or ds.file_meta is None:
        ds.file_meta = FileMetaDataset()
    meta = ds.file_meta
    try:
        meta.MediaStorageSOPClassUID = ds.SOPClassUID
    except Exception:
        pass
    if not getattr(meta, 'TransferSyntaxUID', None):
        if 'PixelData' in ds:
            meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        else:
            meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds.file_meta = meta


# =============================
# Index archives once
# =============================
def index_archives(base_dir: str):
    struct_index, ct_index, plan_index = {}, {}, {}
    zip_paths = []
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith('.zip'):
                zip_paths.append(os.path.join(root, f))

    logger.info(f"Indexing {len(zip_paths)} ZIPs…")
    for zp in zip_paths:
        try:
            with zipfile.ZipFile(zp, 'r') as zf:
                for entry in zf.infolist():
                    name = entry.filename
                    if not name.lower().endswith(('.dcm', '')):
                        continue
                    try:
                        ds = pydicom.dcmread(BytesIO(zf.read(entry)), stop_before_pixels=True, force=True)
                    except Exception:
                        continue

                    modality = str(getattr(ds, 'Modality', '')).upper()
                    sop_class = str(getattr(ds, 'SOPClassUID', ''))

                    if sop_class == UID_RTSTRUCT or modality == 'RTSTRUCT':
                        struct_index[str(ds.SOPInstanceUID)] = {'zip': zp, 'entry': name}

                    if modality == 'CT' and (INDEX_ANY_CT or sop_class == UID_CT_IMAGE):
                        ct_index[str(ds.SOPInstanceUID)] = {
                            'zip': zp,
                            'entry': name,
                            'series_uid': str(getattr(ds, 'SeriesInstanceUID', '')),
                            'sop_class': str(getattr(ds, 'SOPClassUID', '')),
                        }

                    if sop_class == UID_RTPLAN:
                        pid = ds.PatientID.strip() if USE_PATIENT_ID else str(getattr(ds, 'PatientName', '')).strip()
                        lbl = str(getattr(ds, 'RTPlanLabel', '')).strip()
                        ref_struct = None
                        if hasattr(ds, 'ReferencedStructureSetSequence') and ds.ReferencedStructureSetSequence:
                            ref_struct = str(ds.ReferencedStructureSetSequence[0].ReferencedSOPInstanceUID)
                        plan_index[(pid, lbl)] = {'zip': zp, 'entry': name, 'ref_struct_uid': ref_struct}
        except Exception as e:
            logger.error(f"Failed to index {os.path.basename(zp)}: {e}")

    logger.info(
        f"Indexed: {len(plan_index)} plans → {sum(1 for v in plan_index.values() if v['ref_struct_uid'])} with struct refs; "
        f"{len(struct_index)} RTSTRUCTs; {len(ct_index)} CT slices"
    )
    return struct_index, ct_index, plan_index


# =============================
# Main
# =============================
def safe_name(s: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in ('-', '_', '.', ' ') else '_' for ch in (s or ''))[:128].strip() or 'UNK'


def load_existing_ct_keys(path: str) -> set:
    if not os.path.exists(path):
        return set()
    try:
        df = pd.read_csv(path, dtype=str)
        return set(df['ct_key'].dropna().astype(str).tolist())
    except Exception:
        return set()


def append_ct_keys(path: str, rows: list):
    if not rows:
        return
    df = pd.DataFrame(rows)
    header = not os.path.exists(path)
    df.to_csv(path, mode='a', header=header, index=False)


def resolve_anon_id(pid_from_wide: str, ds_struct: pydicom.dataset.FileDataset, id_map: dict) -> str:
    cands = []
    if pid_from_wide:
        cands.append(pid_from_wide.strip())
    for tag in ('PatientID', 'PatientName'):
        v = str(getattr(ds_struct, tag, '')).strip()
        if v:
            cands.append(v)
    for c in cands:
        if c in id_map:
            return id_map[c]
    if pid_from_wide and pid_from_wide in id_map.values():
        return pid_from_wide
    return ''


def fix_contour_image_refs(ds_struct: pydicom.dataset.FileDataset, ct_ix: dict) -> tuple[int, int]:
    """
    Ensure every ContourImageSequence item has a ReferencedSOPClassUID (0008,1150)
    matching the SOP class of the referenced CT slice we're exporting.
    Returns (updated_count, missing_count).
    """
    updated = 0
    missing = 0
    rc_seq = getattr(ds_struct, 'ROIContourSequence', None)
    if not rc_seq:
        return (0, 0)

    for roi in rc_seq or []:
        for ct in getattr(roi, 'ContourSequence', []) or []:
            for ref in getattr(ct, 'ContourImageSequence', []) or []:
                uid = str(getattr(ref, 'ReferencedSOPInstanceUID', '')).strip()
                if not uid:
                    continue
                info = ct_ix.get(uid)
                if not info:
                    # RTSTRUCT references a CT slice we didn't index/export
                    missing += 1
                    continue
                want_cls = info.get('sop_class') or '1.2.840.10008.5.1.4.1.1.2'  # Classic CT, if unknown
                have_cls = str(getattr(ref, 'ReferencedSOPClassUID', '')).strip()
                if have_cls != want_cls:
                    ref.ReferencedSOPClassUID = want_cls
                    updated += 1
    return (updated, missing)



def prune_rtstruct_to_available_ct(ds_struct, available_ct_uids: set) -> tuple[int,int]:
    """
    Drop any ContourImageSequence refs not in available_ct_uids.
    Drop ROIContourSequence items that end with no ContourSequence items.
    Returns: (kept_roi_items, dropped_roi_items).
    """
    rc_seq = getattr(ds_struct, 'ROIContourSequence', None)
    if not rc_seq:
        return (0, 0)

    new_rc = []
    dropped = 0
    for roi in rc_seq or []:
        new_ctseq = []
        for ct in getattr(roi, 'ContourSequence', []) or []:
            imgs = getattr(ct, 'ContourImageSequence', []) or []
            keep_imgs = [ref for ref in imgs
                         if str(getattr(ref, 'ReferencedSOPInstanceUID', '')).strip() in available_ct_uids]
            if keep_imgs:
                ct.ContourImageSequence = keep_imgs
                new_ctseq.append(ct)
        if new_ctseq:
            roi.ContourSequence = new_ctseq
            new_rc.append(roi)
        else:
            dropped += 1
    ds_struct.ROIContourSequence = new_rc
    return (len(new_rc), dropped)
def prune_top_level_image_refs(ds_struct, available_ct_uids: set, ct_ix: dict) -> tuple[int, int, int]:
    """
    Filter top-level ContourImageSequence (3006,0016) and ReferencedImageSequence (0008,1140)
    so they only reference CT SOP Instance UIDs we are actually exporting.
    Also ensure ReferencedSOPClassUID (0008,1150) is present and consistent.
    Returns: (updated_1150_count, removed_ref_items, removed_series_items)
    """
    updated = 0
    removed_refs = 0
    removed_series = 0

    # helper to set 1150
    def set_class(item, uid):
        nonlocal updated
        want = ct_ix.get(uid, {}).get('sop_class') or '1.2.840.10008.5.1.4.1.1.2'  # classic CT fallback
        have = str(getattr(item, 'ReferencedSOPClassUID', '')).strip()
        if have != want:
            item.ReferencedSOPClassUID = want
            updated += 1

    rfor_seq = getattr(ds_struct, 'ReferencedFrameOfReferenceSequence', None) or []
    for rfor in rfor_seq:
        rstud_seq = getattr(rfor, 'RTReferencedStudySequence', None) or []
        new_rstud_seq = []
        for rstud in rstud_seq:
            rser_seq = getattr(rstud, 'RTReferencedSeriesSequence', None) or []
            new_rser_seq = []
            for rser in rser_seq:
                # ContourImageSequence (3006,0016)
                cis = getattr(rser, 'ContourImageSequence', None)
                if cis is not None:
                    keep = []
                    for ci in cis or []:
                        uid = str(getattr(ci, 'ReferencedSOPInstanceUID', '')).strip()
                        if uid and uid in available_ct_uids:
                            set_class(ci, uid)
                            keep.append(ci)
                        else:
                            removed_refs += 1
                    rser.ContourImageSequence = keep

                # ReferencedImageSequence (0008,1140)
                ris = getattr(rser, 'ReferencedImageSequence', None)
                if ris is not None:
                    keep = []
                    for ri in ris or []:
                        uid = str(getattr(ri, 'ReferencedSOPInstanceUID', '')).strip()
                        if uid and uid in available_ct_uids:
                            set_class(ri, uid)
                            keep.append(ri)
                        else:
                            removed_refs += 1
                    rser.ReferencedImageSequence = keep

                # keep this series only if it still has any refs
                has_cis = getattr(rser, 'ContourImageSequence', None)
                has_ris = getattr(rser, 'ReferencedImageSequence', None)
                if (has_cis and len(has_cis) > 0) or (has_ris and len(has_ris) > 0):
                    new_rser_seq.append(rser)
                else:
                    removed_series += 1

            rstud.RTReferencedSeriesSequence = new_rser_seq
            if len(new_rser_seq) > 0:
                new_rstud_seq.append(rstud)
        rfor.RTReferencedStudySequence = new_rstud_seq

    return updated, removed_refs, removed_series


def collect_and_anonymise():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    id_map = read_id_mapping(ID_MAPPING_CSV)
    plan_info = load_plan_info(WIDE_PLAN_CSV)
    roi_map = read_roi_mapping(ROI_MAPPING_CSV)
    struct_ix, ct_ix, plan_ix = index_archives(BASE_DIR)

    summary_rows, files_rows, roi_rows, roi_kept_by_patient_rows = [], [], [], []
    processed_ct_keys = load_existing_ct_keys(CT_KEYS_CSV)
    new_ct_key_rows = []

    skipped_no_mapping = skipped_no_plan_or_struct = 0

    for (pid, plan_label), pinfo in sorted(plan_info.items()):
        # record skeleton
        rec = {
            'patient_original': pid,
            'plan_label': plan_label,
            'anon_id': '',
            'struct_found': False,
            'ct_slices_copied': 0,
            'ct_series_count': 0,
            'rois_kept': 0,
            'rois_dropped': 0,
            'ct_key': '',
            'note': ''
        }
        ct_key = ''

        pidx = plan_ix.get((pid, plan_label))
        if not pidx or not pidx.get('ref_struct_uid'):
            rec['note'] = 'Plan or referenced RTSTRUCT not found'
            skipped_no_plan_or_struct += 1
            summary_rows.append(rec);
            continue

        struct_uid = pidx['ref_struct_uid']
        sinfo = struct_ix.get(struct_uid)
        if not sinfo:
            rec['note'] = 'Referenced RTSTRUCT UID not indexed'
            summary_rows.append(rec);
            continue

        # Load RTSTRUCT
        try:
            with zipfile.ZipFile(sinfo['zip'], 'r') as zf:
                raw_struct_bytes = zf.read(sinfo['entry'])
            ds_struct = pydicom.dcmread(BytesIO(raw_struct_bytes), stop_before_pixels=False, force=True)
        except Exception as e:
            rec['note'] = f"Failed loading RTSTRUCT: {e}"
            summary_rows.append(rec);
            continue

        # Resolve anonymised ID
        anon_id = resolve_anon_id(pid, ds_struct, id_map)
        rec['anon_id'] = anon_id
        if not anon_id:
            rec[
                'note'] = f"No anonymised ID mapping (pid='{pid}', RTSTRUCT.PatientID='{getattr(ds_struct, 'PatientID', '')}', PatientName='{getattr(ds_struct, 'PatientName', '')}')"
            skipped_no_mapping += 1
            summary_rows.append(rec);
            continue

        # ROI filter/rename (no UID changes)
        kept_detail, dropped_names = [], []
        if ALLOW_ROI_FILTER:
            ds_struct_copy = ds_struct.copy() if not RENAMING_ONLY else ds_struct
            kept, dropped, kept_detail, dropped_names = harmonise_and_filter_rtstruct(
                ds_struct_copy,
                roi_map,
                renumber=RENUMBER_ROI,
                drop_unknown=not RENAMING_ONLY,
                ct_uid_set=set(ct_ix.keys()) if REQUIRE_CT_BACKED_CONTOURS else None,
            )
            if kept == 0 and not RENAMING_ONLY:
                # would leave empty contours; revert to original struct
                ds_struct = pydicom.dcmread(BytesIO(raw_struct_bytes), stop_before_pixels=False, force=True)
                rec['rois_kept'] = len(getattr(ds_struct, 'StructureSetROISequence', []) or [])
                rec['rois_dropped'] = 0
            else:
                ds_struct = ds_struct_copy
                rec['rois_kept'] = kept
                rec['rois_dropped'] = dropped
        else:
            rec['rois_kept'] = len(getattr(ds_struct, 'StructureSetROISequence', []) or [])
            rec['rois_dropped'] = 0

        # Label: AnonID_PlanLabel_TotalDose_NumFracs
        td = pinfo.get('total');
        nf = pinfo.get('num_fracs')
        td_str = f"{td:.1f}" if isinstance(td, (int, float)) else ''
        nf_str = ''
        try:
            if nf is not None and str(nf) != '':
                nf_str = str(int(float(nf)))
        except Exception:
            nf_str = str(nf)
        ds_struct.StructureSetLabel = f"{anon_id}_{plan_label}_{td_str}_{nf_str}".strip('_')
        # === Build the set of CT UIDs referenced by the struct (raw) ===
        raw_ref_uids = set()
        for roi in getattr(ds_struct, 'ROIContourSequence', []) or []:
            for ct in getattr(roi, 'ContourSequence', []) or []:
                for ci in getattr(ct, 'ContourImageSequence', []) or []:
                    uid = str(getattr(ci, 'ReferencedSOPInstanceUID', '')).strip()
                    if uid:
                        raw_ref_uids.add(uid)

        available = raw_ref_uids & set(ct_ix.keys())
        missing = raw_ref_uids - set(ct_ix.keys())
        if missing:
            logger.warning(f"{anon_id}/{plan_label}: {len(missing)} contour refs not found in archives (will prune).")

        # === Prune the struct to only CTs we actually have ===
        kept_cnt, dropped_cnt = prune_rtstruct_to_available_ct(ds_struct, available)
        logger.info(
            f"{anon_id}/{plan_label}: ROIContour items -> kept {kept_cnt}, dropped {dropped_cnt} after pruning.")

        # If pruning removed all ROIContour items, skip the case entirely to avoid 'CT only'
        if kept_cnt == 0:
            rec['note'] = 'All contours referenced CTs we do not have — skipping case.'
            summary_rows.append(rec)
            continue
        # prune the TOP-LEVEL references too (3006,0016 and 0008,1140)
        u1150, rm_refs, rm_series = prune_top_level_image_refs(ds_struct, available, ct_ix)
        if u1150 or rm_refs or rm_series:
            logger.info(f"{anon_id}/{plan_label}: top-level refs -> set 1150 on {u1150}, "
                        f"removed {rm_refs} refs, removed {rm_series} empty series")

        # === Make sure each remaining contour image ref has 0008,1150 set to the real CT SOP Class ===
        upd, miss = fix_contour_image_refs(ds_struct, ct_ix)
        if upd or miss:
            logger.info(
                f"{anon_id}/{plan_label}: set ReferencedSOPClassUID (0008,1150) on {upd} contour refs; {miss} refs not found in CT index")


        # ROI log rows
        for row in kept_detail:
            roi_rows.append({
                'anon_id': anon_id, 'plan_label': plan_label, 'ct_key': ct_key,
                'roi_old_name': row['old_name'], 'roi_new_name': row['new_name'],
                'old_number': row['old_number'], 'new_number': row['new_number']
            })
        for dn in dropped_names:
            roi_rows.append({
                'anon_id': anon_id, 'plan_label': plan_label, 'ct_key': ct_key,
                'roi_old_name': dn, 'roi_new_name': '', 'old_number': '', 'new_number': ''
            })

                # collect referenced CTs (from the saved struct)
        # === Build CT list (from pruned ds_struct) ===
        ct_by_series = defaultdict(list)
        for roi in getattr(ds_struct, 'ROIContourSequence', []) or []:
            for contour in getattr(roi, 'ContourSequence', []) or []:
                for ci in getattr(contour, 'ContourImageSequence', []) or []:
                    uid = str(getattr(ci, 'ReferencedSOPInstanceUID', '')).strip()
                    if uid and uid in ct_ix:
                        loc = ct_ix[uid]
                        ct_by_series[loc['series_uid']].append(uid)

        rec['ct_series_count'] = len(ct_by_series)
        # Build a stable CT key from all referenced CT SOPInstanceUIDs
        all_ct_uids = sorted({uid for uids in ct_by_series.values() for uid in uids})
        ct_key = ";".join(all_ct_uids) if all_ct_uids else ""
        rec['ct_key'] = ct_key

        # Skip if already processed same CT set
        if ct_key and ct_key in processed_ct_keys:
            rec['note'] = 'CT already processed — skipping (ct_key match)'
            summary_rows.append(rec)
            continue
        # --- Build kept ROI names from the final, pruned ds_struct ---
        roi_nums_with_images = set()
        for roi in getattr(ds_struct, 'ROIContourSequence', []) or []:
            rn = int(getattr(roi, 'ReferencedROINumber', 0) or 0)
            # keep if at least one contour has at least one image ref
            has_img = False
            for cs in getattr(roi, 'ContourSequence', []) or []:
                imgs = getattr(cs, 'ContourImageSequence', None)
                if imgs and len(imgs) > 0:
                    has_img = True
                    break
            if has_img:
                roi_nums_with_images.add(rn)

        rn2name = {
            int(it.ROINumber): str(getattr(it, 'ROIName', '')).strip()
            for it in (getattr(ds_struct, 'StructureSetROISequence', []) or [])
        }
        kept_names = sorted({rn2name[rn] for rn in roi_nums_with_images if rn in rn2name and rn2name[rn]})

        roi_kept_by_patient_rows.append({
            'anon_id': anon_id,
            'plan_label': plan_label,
            'ct_key': ct_key,  # now populated
            'kept_rois': ';'.join(kept_names)
        })

        # Final output folder
        final_pkg_root = os.path.join(OUTPUT_DIR, safe_name(anon_id), safe_name(plan_label))
        os.makedirs(final_pkg_root, exist_ok=True)

        # ---- RTSTRUCT final write (NO UID EDITS) ----
        struct_dest = os.path.join(final_pkg_root, f"{struct_uid}.dcm")

        # minimal demographics + XNAT policy (no UIDs)
        ds_struct.PatientName = anon_id
        if ANONYMIZE_PATIENT_ID:
            ds_struct.PatientID = anon_id
            ds_struct.AccessionNumber = anon_id
            ds_struct.StudyID = anon_id
        if APPLY_POLICY_TO_RTSTRUCT:
            apply_xnat_policy(ds_struct)

        # make sure file_meta/TS are sane, then save to the FINAL path
        ensure_file_meta(ds_struct)
        ds_struct.save_as(struct_dest, write_like_original=True)

        # log only if it exists (avoids FileNotFoundError if save failed)
        if os.path.exists(struct_dest):
            logger.info(f"Wrote RTSTRUCT: {struct_dest} ({os.path.getsize(struct_dest)} bytes)")
        else:
            logger.warning(f"RTSTRUCT not written as expected: {struct_dest}")

        files_rows.append({'anon_id': anon_id, 'plan_label': plan_label, 'class': 'RTSTRUCT', 'path': struct_dest})

        # ---- CTs final write (NO UID EDITS) ----
        for series_uid, sop_uids in ct_by_series.items():
            for uid in sop_uids:
                loc = ct_ix.get(uid)
                if not loc:
                    continue
                dest_fp = os.path.join(final_pkg_root, f"{uid}.dcm")
                with zipfile.ZipFile(loc['zip'], 'r') as zf:
                    raw = zf.read(loc['entry'])
                ds_ct = pydicom.dcmread(BytesIO(raw), stop_before_pixels=False, force=True)
                # patient identity only + policy (no UIDs)
                ds_ct.PatientName = anon_id
                if ANONYMIZE_PATIENT_ID:
                    ds_ct.PatientID = anon_id
                    ds_ct.AccessionNumber = anon_id
                    ds_ct.StudyID = anon_id
                apply_xnat_policy(ds_ct)
                ensure_file_meta(ds_ct)
                ds_ct.save_as(dest_fp, write_like_original=True)
                files_rows.append({'anon_id': anon_id, 'plan_label': plan_label, 'class': 'CT', 'path': dest_fp})

        if ct_key:
            new_ct_key_rows.append({'ct_key': ct_key, 'anon_id': anon_id, 'plan_label': plan_label})
            processed_ct_keys.add(ct_key)

        if CLEAN_STAGING:
            try:
                shutil.rmtree(pkg_root)
            except Exception:
                pass

        summary_rows.append(rec)

    # Write logs
    pd.DataFrame(summary_rows).to_csv(SUMMARY_CSV, index=False)
    pd.DataFrame(files_rows).to_csv(FILES_CSV, index=False)
    if roi_rows:
        pd.DataFrame(roi_rows).to_csv(ROI_LOG_CSV, index=False)
    append_roi_kept_rows(ROI_PATIENT_CSV, roi_kept_by_patient_rows)
    if new_ct_key_rows:
        append_ct_keys(CT_KEYS_CSV, new_ct_key_rows)

    logger.info(f"Done. Summary: {SUMMARY_CSV}; Files: {FILES_CSV}; ROI log: {ROI_LOG_CSV if roi_rows else 'n/a'}; "
                f"ROI kept-by-patient: {ROI_PATIENT_CSV if roi_kept_by_patient_rows else 'n/a'}; "
                f"CT keys updated: {CT_KEYS_CSV if new_ct_key_rows else 'n/a'}")


if __name__ == '__main__':
    collect_and_anonymise()

import os
import uuid
import pydicom
from pydicom.tag import Tag

# === Configuration ===
PASS_PHRASE = 'CLEA'
NAMESPACE_UUID = uuid.NAMESPACE_DNS
FALLBACK_ROOT = '1.2.840.4267.30'


# === Helper Functions ===
def find_common_root(uids):
    """
    Return the longest common numeric prefix (OID root) among non-empty UID strings.
    """
    # Filter out None or empty
    valid_uids = [uid for uid in uids if isinstance(uid, str) and uid]
    if not valid_uids:
        return ''
    split_uids = [uid.split('.') for uid in valid_uids]
    common_parts = []
    for parts in zip(*split_uids):
        if all(part == parts[0] for part in parts):
            common_parts.append(parts[0])
        else:
            break
    return '.'.join(common_parts)


def deterministic_uid(orig_uid: str, root: str) -> str:
    name = orig_uid + PASS_PHRASE
    u5 = uuid.uuid5(NAMESPACE_UUID, name)
    return f"{root}.{u5.int}"


def build_uid_maps(dicom_files, root):
    study_map, series_map, sop_map, struct_map, dose_map, frame_map = ({},) * 6
    for fp in dicom_files:
        ds = pydicom.dcmread(fp, stop_before_pixels=True)
        for tag, m in [
            ('StudyInstanceUID', study_map),
            ('SeriesInstanceUID', series_map),
            ('SOPInstanceUID', sop_map),
            ('DoseReferenceUID', dose_map),
            ('FrameOfReferenceUID', frame_map)
        ]:
            orig = getattr(ds, tag, None)
            if orig and orig not in m:
                m[orig] = deterministic_uid(orig, root)
        if getattr(ds, 'Modality', None) == 'RTSTRUCT':
            orig = getattr(ds, 'StructureSetUID', None)
            if orig and orig not in struct_map:
                struct_map[orig] = deterministic_uid(orig, root)
    return study_map, series_map, sop_map, struct_map, dose_map, frame_map


def anonymize_file(fp, out_dir, maps):
    study_map, series_map, sop_map, struct_map, dose_map, frame_map = maps
    ds = pydicom.dcmread(fp)
    meta = ds.file_meta

    # Update file-meta SOP Instance UID
    ms = meta.get('MediaStorageSOPInstanceUID', None)
    if ms in sop_map:
        meta.MediaStorageSOPInstanceUID = sop_map[ms]

    # Replace core UIDs
    for tag, m in [
        ('StudyInstanceUID', study_map),
        ('SeriesInstanceUID', series_map),
        ('SOPInstanceUID', sop_map),
        ('DoseReferenceUID', dose_map),
        ('FrameOfReferenceUID', frame_map)
    ]:
        val = getattr(ds, tag, None)
        if val in m:
            setattr(ds, tag, m[val])

    # RTSTRUCT specifics
    if getattr(ds, 'Modality', None) == 'RTSTRUCT':
        ss = getattr(ds, 'StructureSetUID', None)
        if ss in struct_map:
            ds.StructureSetUID = struct_map[ss]
        for ref_for in getattr(ds, 'ReferencedFrameOfReferenceSequence', []):
            fo = getattr(ref_for, 'FrameOfReferenceUID', None)
            if fo in frame_map:
                ref_for.FrameOfReferenceUID = frame_map[fo]
            for rs in getattr(ref_for, 'RTReferencedStudySequence', []):
                ri = getattr(rs, 'ReferencedSOPInstanceUID', None)
                if ri in series_map:
                    rs.ReferencedSOPInstanceUID = series_map[ri]
        for roi in getattr(ds, 'ROIContourSequence', []):
            for ct in getattr(roi, 'ContourSequence', []):
                for img in getattr(ct, 'ContourImageSequence', []):
                    uid = getattr(img, 'ReferencedSOPInstanceUID', None)
                    if uid in sop_map:
                        img.ReferencedSOPInstanceUID = sop_map[uid]
        for elem in ds.iterall():
            if elem.tag == Tag(0x0008, 0x1155) and elem.value in sop_map:
                elem.value = sop_map[elem.value]

    # Preserve meta class identifiers
    impl_uid = meta.get('ImplementationClassUID')
    impl_ver = meta.get('ImplementationVersionName')
    meta.MediaStorageSOPClassUID = ds.SOPClassUID
    if impl_uid:
        meta.ImplementationClassUID = impl_uid
    if impl_ver:
        meta.ImplementationVersionName = impl_ver
    if not getattr(meta, 'TransferSyntaxUID', None):
        meta.TransferSyntaxUID = meta.get('TransferSyntaxUID') or pydicom.uid.ExplicitVRLittleEndian
    ds.file_meta = meta

    # Save
    pid = getattr(ds, 'PatientID', 'Unknown')
    patient_folder = os.path.join(out_dir, pid)
    os.makedirs(patient_folder, exist_ok=True)
    ds.save_as(os.path.join(patient_folder, os.path.basename(fp)), write_like_original=True)


def find_dicom_files(root_dir):
    files = []
    for r, _, names in os.walk(root_dir):
        for fname in names:
            if fname.lower().endswith('.dcm'):
                files.append(os.path.join(r, fname))
    return files


def validate_references(ct_dir, rtstruct_paths):
    ct_uids = set()
    for root, _, names in os.walk(ct_dir):
        for fname in names:
            if fname.lower().endswith('.dcm'):
                ds = pydicom.dcmread(os.path.join(root, fname), stop_before_pixels=True)
                ct_uids.add(ds.SOPInstanceUID)
    for rt in rtstruct_paths:
        ds = pydicom.dcmread(rt)
        missing = [ref.ReferencedSOPInstanceUID
                   for roi in getattr(ds, 'ROIContourSequence', [])
                   for contour in getattr(roi, 'ContourSequence', [])
                   for ref in getattr(contour, 'ContourImageSequence', [])
                   if ref.ReferencedSOPInstanceUID not in ct_uids]
        if missing:
            print(f"❌ Dangling references in {rt}:")
            for uid in missing:
                print(f"   • {uid}")
        else:
            print(f"✅ All references valid for {rt}")


def main(input_dir, output_dir):
    files = find_dicom_files(input_dir)
    all_uids = []
    for f in files:
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        for tag in (
        'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID', 'DoseReferenceUID', 'FrameOfReferenceUID'):
            val = getattr(ds, tag, None)
            if val:
                all_uids.append(val)
        if getattr(ds, 'Modality', None) == 'RTSTRUCT':
            ss = getattr(ds, 'StructureSetUID', None)
            if ss:
                all_uids.append(ss)
    root = find_common_root(all_uids) or FALLBACK_ROOT
    print(f"Using org-root: {root}")

    maps = build_uid_maps(files, root)
    rtstructs = []
    for f in files:
        anonymize_file(f, output_dir, maps)
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        if ds.Modality == 'RTSTRUCT':
            rtstructs.append(os.path.join(output_dir, ds.PatientID, os.path.basename(f)))

    validate_references(output_dir, rtstructs)


from pathlib import Path


if __name__ == '__main__':
    # Uncomment to hardcode or prompt
    inp = OUTPUT_DIR
    outp = 'HeadNodeBatchANON13'
    main(inp, outp)

