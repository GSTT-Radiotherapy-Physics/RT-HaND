# DICOM Ingestion from PACS

The XNAT data lake will be updated with imaging data on a 3-monthly basis for two streams of ingestion:

- Ingestion of data for new patients
- Ongoing ingestion of data for existing patients

The data flow diagram for this process is shown below.

![image](https://github.com/user-attachments/assets/99eb20de-3294-436c-a6e1-f7d51c409e12)

Ingestion for both streams will follow a similar process:

### Step 1. Query PACS for associated studies

To update the XNAT repository, PACS should be queried for studies associated with each patient ID.

- For new patients, PACS should be queried for ALL studies
- For ongoing ingestion, PACS should be queried for studies within a specified date range (e.g. 3 month date range, since the previous ingestion)

Collation of patient lists will be carried out by the project administrator and provided to the CSC team. The CSC team will return to the administrator the following fields for available data in PACS:

| Accession Number| Patient ID | Study Date| Study Description| Study UID|
|-                |-           |-          |-                 |-         |

### Step 2. Remove Unwanted Studies
Only studies related to the diagnosis, staging, progression or ongoing monitoring of treatment side effects of HNC should be ingested into XNAT.  Studies should be filtered by study description to include only relevant scans.  A list of study descriptions to include and exclude is saved [here](../Appendix/12a_RT-HaND_I_Imaging_Study_Descriptions-Known_Include_Exclude.xlsx).  Updates in scanning protocols and imaging machines mean that some studies have descriptions which don't appear on this list.  The project administrator should sort through these study names and update the include/exclude list appropriately.  Any queries about which studies should be included should be addressed by the clinical fellow.

Studies that have been included so far:
- All staging FDG nuclear medicine scans (NM)
- All staging (e.g. CT chest/abdomen and pelvis)
- Relevant anatomy (head and neck area) CTs and MRIs
- All dental x-ray (XR) studies
- Video fluoroscopy (VF) studies
- Unspecified CTs - inspected and included if relevant

### Step 3. Associate Patient MRN with NHS ID
Data pulled from PACS will be associated with the patient's MRN, whereas the XNAT data lake is identified through NHS ID.  In order to ingest from PACS, studies must be linked to an NHS ID.  An additional column must be added to the table.  A VLOOKUP formula can be used alongside the master patient list to complete this column. 

### Step 4. Ingestion
The table should be saved in .csv format and sent to the CSC team for ingestion into XNAT.
  
### Step 5. Manage Failed Ingestions
Following ingestion of the studies into XNAT, there may be some failures. These will need to be assessed on a case-by-case basis.  Unresolved failed ingestions must be recorded for future reference.

### Step 6. Update Data Availability Document
