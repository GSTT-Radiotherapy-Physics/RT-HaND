#this script does an okay job at creating folders of plan, dose cube, structure set and CT based on the plan name. It does a good job of binning off extraneous CBCTs and not relevant dose files. It does not work for the Monaco patients who were reconstructed incorrectly and as such do not have a plan with a field associated with them. 

import os
import shutil
import pydicom

def extract_uids_and_plan_name_from_rt_plan(plan_file_path):
    try:
        dicom_file = pydicom.dcmread(plan_file_path, stop_before_pixels=True)

        # Extract the RT Plan Name
        plan_name = dicom_file.get((0x300a, 0x0002), None).value if dicom_file.get((0x300a, 0x0002), None) else "UnknownPlan"

        # Extract the Study Instance UID
        study_instance_uid = dicom_file.get("StudyInstanceUID", None)

        # Extract the Referenced Structure Set UID
        referenced_structure_set_uid = None
        if hasattr(dicom_file, "ReferencedStructureSetSequence"):
            referenced_structure_set_uid = dicom_file.ReferencedStructureSetSequence[0].ReferencedSOPInstanceUID

        # Extract the Patient ID
        patient_id = dicom_file.get("PatientID", "UnknownPatient")

        return plan_name, study_instance_uid, referenced_structure_set_uid, patient_id

    except Exception as e:
        print(f"Error reading RT Plan file: {e}")
        return None, None, None, None


def find_dicom_files(root_dir, study_instance_uid=None, modality=None, sop_instance_uid=None):
    found_files = []

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            try:
                dicom_file = pydicom.dcmread(file_path, stop_before_pixels=True)

                if modality and dicom_file.Modality != modality:
                    continue
                if study_instance_uid and dicom_file.StudyInstanceUID != study_instance_uid:
                    continue
                if sop_instance_uid and dicom_file.SOPInstanceUID != sop_instance_uid:
                    continue

                found_files.append(file_path)
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")

    return found_files


def copy_and_rename_files(files, destination_dir, new_filename_prefix=None):
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    for file_path in files:
        # Determine the new filename if a prefix is provided
        if new_filename_prefix:
            new_filename = f"{new_filename_prefix}.dcm"
            destination_path = os.path.join(destination_dir, new_filename)
        else:
            destination_path = os.path.join(destination_dir, os.path.basename(file_path))

        shutil.copy2(file_path, destination_path)
        print(f"Copied {file_path} to {destination_path}")


def main():
    root_dir = input("Enter the root directory to search for RT Plan files: ")
    destination_root = input("Enter the root destination directory for the copied files: ")

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            try:
                dicom_file = pydicom.dcmread(file_path, stop_before_pixels=True)

                if dicom_file.Modality == "RTPLAN":
                    print(f"\nProcessing RT Plan file: {file_path}")
                    plan_name, study_instance_uid, referenced_structure_set_uid, patient_id = extract_uids_and_plan_name_from_rt_plan(file_path)

                    if not study_instance_uid:
                        print("Critical UIDs are missing, skipping this plan.")
                        continue

                    # Create destination directory for this plan with both Patient ID and Plan Name
                    plan_destination_dir = os.path.join(destination_root, f"{patient_id}_{plan_name}")
                    os.makedirs(plan_destination_dir, exist_ok=True)

                    # Copy the RT Plan file
                    copy_and_rename_files([file_path], plan_destination_dir)

                    # Find and copy the CT files
                    ct_files = find_dicom_files(root_dir, study_instance_uid=study_instance_uid, modality="CT")
                    if ct_files:
                        copy_and_rename_files(ct_files, plan_destination_dir)
                    else:
                        print("No CT files found.")

                    # Find and copy the Dose file
                    dose_files = find_dicom_files(root_dir, study_instance_uid=study_instance_uid, modality="RTDOSE")
                    if dose_files:
                        copy_and_rename_files(dose_files, plan_destination_dir)
                    else:
                        print("No Dose files found.")

                    # Find and copy the Structure Set file, and rename it
                    if referenced_structure_set_uid:
                        structure_set_file_path = find_dicom_files(root_dir, sop_instance_uid=referenced_structure_set_uid, modality="RTSTRUCT")
                        if structure_set_file_path:
                            structure_set_name = dicom_file.get((0x3006, 0x0002), None).value if dicom_file.get((0x3006, 0x0002), None) else "UnknownStruct"
                            new_filename_prefix = f"{patient_id}_{plan_name}_{structure_set_name}"
                            copy_and_rename_files(structure_set_file_path, plan_destination_dir, new_filename_prefix)
                        else:
                            print("No Structure Set files found.")

            except Exception as e:
                print(f"Error processing file {file_path}: {e}")


if __name__ == "__main__":
    main()
