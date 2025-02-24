#Script to write DICOM header to .csv file
#User selects DICOM file and directory for csv file
#csv file generated with name PatientID_Modality_AcquisitionDate
import os
import pydicom
import csv
from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory

#Function to choose the input DICOM file
def get_input_file():
    """Open a file dialog to select the DICOM file."""
    root = Tk()
    root.withdraw() # Hide the root window
    root. attributes('-topmost', True) # Bring the dialog to the front
    file_path = askopenfilename(
        title="Select DICOM File",
        filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")]
    )
    return file_path

#Function to choose the output directory using a dialog
def get_output_directory():
    """Open a file dialog to select an output directory."""
    root = Tk()
    root.withdraw() #hide the root window
    root.attributes('-topmost', True) #Bring dialog to the front
    directory = askdirectory(title="Select Output Directory")
    return directory

#Let the user choose the input DICOM file
dicom_file_path = get_input_file()

#Check if the user canceled the file selection
if not dicom_file_path:
    print("No input file selected. Exiting.")
    exit()

#Let the user choose the output directory
output_directory = get_output_directory()

#Check if the user canceled the directory selection
if not output_directory:
    print("No output directory selected.  Exiting.")
    exit()

#Read the DICOM file
ds = pydicom.dcmread(dicom_file_path)

#Extract Patient ID, Modality and Acquisition Date for naming
patient_id = getattr(ds, "PatientID", "UnknownID")
modality = getattr(ds, "Modality", "UnknownModality")
acquisition_date = getattr(ds, "AcquisitionDate", "UnknownDate")

#Format the acquisition date (if available)
if acquisition_date != "UnknownDate":
    acquisition_date = acquisition_date[:8] #Ensure it is in YYYYMMDD format

#Construct the output filename
csv_filename = f"{patient_id}_{modality}_{acquisition_date}.csv"
csv_output_path = os.path.join(output_directory, csv_filename)

# Recursive function to process elements
def process_element(element, parent_tag=""):
    #Processes a single DICOM element, handling nested sequences.
    rows = []
    tag = f"{parent_tag}{element.tag}" if parent_tag else str(element.tag)
    name = element.name
    vr = element.VR

    if element.tag == (0x7FE0, 0x0010):
        return rows #skip this element

    # Handle sequences (nested datasets)
    if element.VR == "SQ":  # Sequence of Items
        for i, item in enumerate(element.value):
            item_tag = f"{tag}[{i}]"
            for sub_elem in item:
                rows.extend(process_element(sub_elem, parent_tag=item_tag + "/"))
    else:
        # Handle regular elements
        value = element.value

        # Handle multi-values
        if isinstance(value, (list, pydicom.multival.MultiValue)):
            value = "; ".join(map(str, value))
        rows.append([tag, name, vr, value])
    return rows

# Read the DICOM file
ds = pydicom.dcmread(dicom_file_path)

# Write to CSV
with open(csv_output_path, mode="w", newline="", encoding="utf-8") as csv_file:
    csv_writer = csv.writer(csv_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)

    # Write the header
    csv_writer.writerow(["Tag", "Name", "VR", "Value"])

    # Process all top-level elements
    for elem in ds:
        csv_writer.writerows(process_element(elem))

print(f"DICOM header exported to {csv_output_path}")
