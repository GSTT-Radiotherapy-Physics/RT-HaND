# Updating from PACS

## Introduction
Diagnostic and follow-up imaging for Head and Neck Cancer patients available up until the implementation of EPIC (4th October 2023) were ingested into XNAT. Only scans considered pertinent by H&N clinicians to the diagnosis, staging, treatment and follow-up of head and neck cancer patients were ingested, a summary can be seen in Appendix 1 or the full inclusion/exclusion criteria are in document 12a RT-HaND_I Imaging Study Descriptions, known Include vs Exclude.

As of 4/10/23 (the date to which the retrospective cohort data is up-to-date currently), around 50% of patients in the cohort were still alive. Future imaging data for these patients will also therefore require curation, ingestion and storage within RT-HaND_I in XNAT. This can include further imaging from PACS or Radiotherapy Treatment from Aria. The same methodologies as the initial ingestions of these patients data can mostly be employed and are detailed below. 

## Background

PACS (Sectra) was queried for the study descriptions and accession numbers of all diagnostic imaging sessions contained for each patient. The resultant study descriptions returned were used to filter the accession numbers to enable the selection of the imaging sessions to ensure only relevant data was ingested using the REST-API into the data lake. Study descriptions considered relevant were any orders pertinent to the diagnosis, staging, progression or ongoing monitoring of treatment side effects of HNC. This included all staging FDG nuclear medicine scans (NM), all staging (e.g. CT chest/abdomen and pelvis) and relevant anatomy (head and neck area) CTs and MRIs and all dental x-ray (XR) and video fluoroscopy (VF) studies. Unspecified CTs were inspected and included if relevant. A brief summary is shown in Appendix 1. The data flow diagram for this process is shown below.

![image](https://github.com/user-attachments/assets/99eb20de-3294-436c-a6e1-f7d51c409e12)

## Ingestion: 
### Existing patients imaging data update (aka prospective imaging data collection of existing patients)
To update the lake for previous retrospective patients, PACS should be queried for new studies since the last ingestion. The descriptions should be used to select the studies for ingestion. There is a list of agreed include and exclude studies to use to initially filter the list. This can be found in 012a: Imaging Study Descriptions known Include vs Exclude criteria. It is likely that not all study descriptions will be included on either the include/exclude list. This is due to updates in scanning protocols and new machines. A clinician should be consulted regarding the new study descriptions and the include/exclude lists updated accordingly. With imaging studies to be ingested filtered out, CSC can then ingest via REST-API with access to the PACS-XNAT pipeline given with respect to clinical priorities.  
Patients known to be deceased should not be included in this query. A data extract from EDW can confirm known deceased patients.

### New patients image data upload (prospective imaging data collection of new patients)
Separately, PACS should be queried for new patients. There should be no date limitation on when these studies were performed. The descriptions should be used to select the studies for ingestion as above. After the initial data extraction of these patients, they should be transferred to the “existing” patient list and follow the above patient update pathway after the initial harvest.

## Updating the data availability summary spreadsheet
### Gathering ingestion information
After all the PACS images have been successfully ingested, a summary spreadsheet of each type of imaging session can be downloaded (e.g. MRI, CT, planar x-ray) from the front end of XNAT.
The imaging session spreadsheets should be in the form of 5 columns. The first column is Subject and the second is Date. Unfortunately, not all the same datatypes are available for each type of scan and so a best guess approximation of most useful parameters was employed for the final 3 columns. These are shown in the below table. They are saved as custom filters in XNAT but can easily be reconstructed in XNAT if not available. The spreadsheets should each be saved as the “Scan Type”.csv e.g. MR.csv. The below table displays the expected parameters within each spreadsheet.

| Session Type | Session Description | Column 1 | Column 2 | Column 3 | Column 4 | Column 5 |
|-------------|---------------------|---------|---------|---------|---------|---------|
| MR          | MRI scan            | Subject | Date    | MR ID   | Scanner | Scans   |
| CT          | CT scan             | Subject | Date    | XNAT_CTSESSIONDATA ID | UID | Scans   |
| PET         | PET-CT scan         | Subject | Date    | XNAT_PETSESSIONDATA ID | UID | Scans   |
| CR          | Dental x-ray        | Subject | Date    | XNAT_CRSESSIONDATA ID | ID  | Session |
| DX          | Dental x-ray        | Subject | Date    | XNAT_DXSESSIONDATA ID | UID | Scans   |
| RF          | Video swallow       | Subject | Date    | XNAT_RFSESSIONDATA ID | ID  | Session |
| SR          | Nuclear medicine    | Subject | Date    | XNAT_SRSESSIONDATA ID | ID  | Creator |
| XA          | Video swallow       | Subject | Date    | XNAT_XASESSIONDATA ID | ID  | Creator |

“NM” is an imaging type available however only contains 1 patient’s 4 bone density scans currently and so is not necessary to include. Similarly, there are 33 “CE” sessions (dental x-rays) where it is not possible to download the data with the subject available and so these are not included. There is only 1 ultrasound scan and so this is not included.

## Gathering failures to ingest via XNAT
The CSC team will return a list of ingestion failures via .csv file of json code. This list contains the patient ID, accession number, study description and UID of the studies that could not be ingested via XNAT. This can be probed to check that the current failure rates are in line with historic failure rates and that there is not a pipeline issue.

In the preparation of the HN XNAT database, in a population of xx patients, upload failure rates were approximately 7% for CTs & MRIs with all investigated failures being due to imaging sessions being cancelled, images being found under different accession numbers or images being scheduled but not completed or no images available on PACS.

Failure rates for NM, Video and XR were typically higher and all presented examples where images are available on PACS but are not ingested by XNAT. This included some PET-CTs which are extremely likely to be useful for future research. For this reason, we documented accession numbers that existed but that were not ingested so that individual researchers can decide if they want to manually extract this information to increase their study numbers. For many of the scans it will be obvious that the accession number was unused and therefore no images were ingested because there was a corresponding scan the week after or the images are attached to another study from the same day, but for cases such as the un-ingested PET-CTs we hope it will be useful.

Scans scheduled for 01-01-2099 are explicitly excluded from this list. This list also serves a record to try to re-ingest the cases should XNAT or PACS updates allow the flow of these images from one system to another. Currently XNAT cannot tell if a scan on PACS has been “cancelled” or if there are no images available.  

A python script has been written which transforms the .json output into a file that can be appended to the EDW data record. The script cleans out the multiple quotation marks and gaps and unexpected data forms and transforms the data into a 5 column table in the same form as the above XNAT table with ID, study date, accession number, study description and study instance UID returned. The output contained patients Hospital IDs so an additional section of the script takes each hospital ID and finds the corresponding NHS number so that it can be attached to the EDW data extract.

## Creating a master spreadsheet of all data in XNAT and all experienced failures of ingestion
All version-controlled python scripts are stored within the RTPHYS GitHub. Version 1.0 for both scripts are also contained within the appendix for reference. Patients without NHS numbers are stored within the XNAT database as NN_patientID. Care must be taken when updating the spreadsheet that there are no patients with blank NHS numbers, as  this is likely to break the code despite efforts to account for blank subjects.

### Expected inputs:
-	8 .csvs downloaded from XNAT of MR, CT, PET, CR, DX, RF, SR, XA data as described above and named MR.csv, CT.csv, PET.csv, CR.csv, DX.csv, RF.csv, SR.csv and XA.csv accordingly, saved within a dated folder.  
-	1 .csv file of Subject (NHS number) and Reference Date (RT start date) only, called “reference_dates” saved within a dated folder. Patients without NHS numbers should be included using their XNAT subject ID: NN_patientID  
-	1 .txt file of json output from failed ingestions called “PACs-failures.txt”.  
-	1 .csv file of HospitalID & NHSNumber only called “HospitalID-NHSNumber.csv”.  

## Steps:
-	Prepare files described above.  
-	Run PACSIngestionErrorSummary script first, this is required as input for XNATImagingSummary script.  
-	Copy output from PACS ingestion error summary script to the location the python script is being run from as the 8 downloaded .csvs.  
-	Run XNATImagingSummary.py adjusting output file name as desired.  
-	Return output to EDW.  

## Anticipated potential future improvements
-	All HospitalIDs are “old” style GSTT patient IDs but PACS still allows the querying of these so they do not need to be updated.  
-	PACS failures to ingest need to be added to the previous PACS failures to ingest txt file so that previous data is not lost when updating the data availability sheets.  
-	Currently the EDW update  is performed manually. Potential future improvements are for the EDW to look for a location on the shared drive to absorb the summary spreadsheet to minimise manual processes and human involvement.  

## Roles and responsibilities

| Role                                       | Responsibility                        |
|--------------------------------------------|--------------------------------------|
| Provide retrospective and prospective patient list | XNAT admin (with EDW assistance)    |
| Query PACS for new patient data           | CSC                                  |
| Choose scans for ingestion                | XNAT admin with clinician input      |
| Ingest scans via REST-API                 | CSC                                  |
| Document failures via .json                | CSC                                  |
| Investigate failures                       | XNAT admin                           |
| Update available data information & known failures | XNAT admin                     |
| Upload available data information to EDW  | TY (As of Sept 2024)                 |




_Note:  This SOP is an amalgamation of the original documents '012 RT-HaND_I; Updating from PACS- Technical Guide' and '19b RT-HaND_I SOP work instructions for maintenance and growth of the database: Pre-EPIC Cohort'._
