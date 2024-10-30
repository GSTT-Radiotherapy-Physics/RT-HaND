#This code is useful for adding back in dicom tags that CSC's anonymisation script MIGHT have scrubbed out that are required if patients are to go back into Eclipse. Of note, structure set date and time are required RT structure set characteristics to be permitted into Eclipse!

import os
import pydicom
import csv
from datetime import datetime


def load_patient_data_from_csv(csv_file):
    """Load patient data from the CSV file into a dictionary."""
    patient_data = {}
    with open(csv_file, newline='') as csvfile:
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            old_patient_id = row['old_patient_id']
            patient_data[old_patient_id] = {
                'new_patient_id': row['new_patient_id'],
                'new_patient_name': row['new_patient_name'],
                'new_patient_sex': row['new_patient_sex']
            }
    return patient_data


def modify_dicom_for_patient(dicom_data, new_patient_id, new_patient_name, new_patient_sex, new_structure_set_name,
                             new_structure_set_label, operator_name="Unknown"):
    """Modify DICOM metadata for the given patient."""

    # Modify the relevant tags
    dicom_data.PatientID = new_patient_id
    dicom_data.PatientName = new_patient_name
    dicom_data.PatientSex = new_patient_sex

    # Check if the file is an RT Structure Set
    if dicom_data.Modality == "RTSTRUCT":
        print(f"Processing RT Structure Set for new PatientID: {new_patient_id}")

        # Add or modify StructureSetName (3006,0002)
        dicom_data.StructureSetName = new_structure_set_name

        # Add or modify StructureSetLabel (3006,0002)
        dicom_data.StructureSetLabel = new_structure_set_label

        # Add Operators' Name (0008,1070) if missing
        if not hasattr(dicom_data, 'OperatorsName'):
            dicom_data.OperatorsName = operator_name

        # Add Structure Set Date (3006,0008) and Time (3006,0009)
        current_date = datetime.now().strftime("%Y%m%d")
        current_time = datetime.now().strftime("%H%M%S")
        if not hasattr(dicom_data, 'StructureSetDate'):
            dicom_data.StructureSetDate = current_date
        if not hasattr(dicom_data, 'StructureSetTime'):
            dicom_data.StructureSetTime = current_time


def process_dicom_files(input_folder, output_folder, patient_data, new_structure_set_name, new_structure_set_label,
                        operator_name="Unknown"):
    """Process DICOM files in the folder and modify them based on the patient data."""

    for root, dirs, files in os.walk(input_folder):
        for file in files:
            # Check if the file is a DICOM file
            if file.endswith(".dcm"):
                dicom_path = os.path.join(root, file)
                # Read the DICOM file
                dicom_data = pydicom.dcmread(dicom_path)
                old_patient_id = dicom_data.PatientID

                # Check if the current PatientID is in the patient_data dictionary
                if old_patient_id in patient_data:
                    patient_info = patient_data[old_patient_id]
                    new_patient_id = patient_info['new_patient_id']
                    new_patient_name = patient_info['new_patient_name']
                    new_patient_sex = patient_info['new_patient_sex']

                    print(f"Modifying DICOM for PatientID: {old_patient_id} -> {new_patient_id}")

                    # Modify the DICOM data
                    modify_dicom_for_patient(dicom_data, new_patient_id, new_patient_name, new_patient_sex,
                                             new_structure_set_name, new_structure_set_label, operator_name)

                    # Create the patient's folder inside the output directory
                    patient_output_folder = os.path.join(output_folder, new_patient_id)
                    if not os.path.exists(patient_output_folder):
                        os.makedirs(patient_output_folder)

                    # Save the modified DICOM file in the new patient's folder
                    output_dicom_path = os.path.join(patient_output_folder, f"{new_patient_id}_{file}")
                    dicom_data.save_as(output_dicom_path)
                    print(
                        f"Saved modified file for PatientID: {old_patient_id} as {new_patient_id} in {patient_output_folder}")


# Example usage
input_folder = "XERO/XERO6"
output_folder = "XERO/XERO6EDITED"  # Parent output folder where each patient folder will be created
csv_file = "XERO/newid_sex.csv"
new_structure_set_name = "StructureSet"
new_structure_set_label = "StructureSet"
operator_name = "DEFAULT_OPERATOR"  # Optional: Set the operator's name
# Load patient data from the CSV file
patient_data = load_patient_data_from_csv(csv_file)

# Process the DICOM files based on the loaded patient data
process_dicom_files(input_folder, output_folder, patient_data, new_structure_set_name, new_structure_set_label, operator_name)
