# RT DICOM Ingestion from ARIA

The XNAT data lake will be updated with radiotherapy DICOM data on a 3-monthly basis for two streams of ingestion:

1. Ingestion of data for new patients
2. Ongoing ingestion of data for existing patients

Ingestion for both streams will follow a similar process:

### Step 1. Query ARIA for associated studies
To update the XNAT repository, ARIA should be queried for studies associated with each patient ID.
- For new patients, ARIA should be queried for ALL studies
- For ongoing ingestion, ARIA should be queried for studies within a specified date range (e.g. 3 month date range, since the previous ingestion)

Collation of patient lists will be carried out by the project administrator and provided to the CSC team.  The CSC team will return to the administrator the following fields for available data in ARIA:

| patientId| studyInstanceUID | studyId| accessionNumber| studyDate| studyDescription|
|-|-|-|-|-|-|

Most of the contents of this table will be images- typically CT scans to which other DICOM objects are attached, or other pre-treatment imaging such as MRI or PET-CT scans.  The non-RT-planning-CT images tend to have accession numbers associated with them, whereas the RT planning CT studies do not.

### Step 2. Remove Irrelevant Studies
Some of the studies found in the ARIA query will not need to be ingested into XNAT.  Irrelevant studies mostly consist of 

### Step 3. Assign Study Descriptions
For the above table, the StudyDescription field will be blank


In the ingestion of the retrospective cohort most patients were treated in Mosaiq and so details on their prescription, completed fractions and radiotherapy start and end dates were taken from EDW and stored within RT-HaND_C in EDW as this is treatment information. The patients treated through Aria had this data manually compiled.

Currently CSC are trying to connect Aria’s database containing this prescription and treatment information to a similar warehousing system so that these radiotherapy details do not need to be complied manually. The database containing these radiotherapy details is called “AURA”. Eclipse scripting is another potential method that could locate a lot of these pieces of data to minimise manual data curation in future. 

Study instance can contain multiple objects, i.e. RT study instance will contain the RT image, plan, SS, dose.  If there is an accession number, this means that it is a pre-treatment imaging study.  If there is only one, can assume this is an RT study.  Currently the solution is to manually look into the rest.  If there are duplicates, rename these as XNAT won't allow duplicates.  Also need to remove any verifications.  Date tends to refer to CT acquisition date.  Electron and ortho can be omitted, but would be useful to store plans for CT-planned electrons.

Patient IDs were provided to Clinical Scientific Computing (CSC). CSC provide a list of study descriptions, accession numbers, dates of what XNAT can see within Aria and session names are constructed based on the data types returned for naming in XNAT. Names of sessions were constructed following the below pattern: 

**Table 1: Naming conventions in XNAT and data elements transferred where CT refers to planning CT, RTSS= Radiotherapy Structure set, RTDose= RT Dosecube file, RTPlan= RT Plan file, reg = registrations to planning CT, CBCT SS= Structure set associated with CBCT, RTRecords= beam delivery records produced by Aria.  The session names were returned to CSC in a .csv file where a custom script was used to ingest the indicated sessions with the given names. Imaging sessions were stored under the patient’s identifier within XNAT (NHS number). **


| RT session type examples                                      | Labelling convention                                      | Example                                      | Data element examples (“scans”) stored as DICOM files |
|--------------------------------------------------------------|----------------------------------------------------------|----------------------------------------------|------------------------------------------------------|
| Pre-treatment imaging                                        | PatientAriaID_RT_year_AccessionNumber                    | 3456789_RT_2017_RJxxxxxxxxxx               | Diagnostic MRI or CT or PET-CT scans, regs.          |
| RT session                                                  | PatientAriaID_RT_year                                    | 3456789_RT_2017                            | CT, RTSS, RTDose, RTPlan and for post Aria patients; CBCTs, CBCT SS and regs and RTRecords. |
| RT session replan                                           | PatientAriaID_RT_year_REPLAN/RESCAN                      | 3456789_RT_2017_REPLAN                     | CT, RTSS, RTDose, RTPlan, reg, CBCTs, CBCT SS and regs and RTRecords. |
| RT session (multiple within 1 year e.g. palliative mets)    | PatientAriaID_RT_year_BodyPartTreated                    | 3456789_RT_2017_SPINE <br> 3456789_RT_2017_WHOLEBRAIN | CT, RTSS, RTDose, RTPlan |
| On-treatment CBCT (pre-Aria)                                | PatientAriaID_RT_year_CBCT                               | 3456789_RT_2017_CBCT                       | CBCT scan, reg, RTSS |
| Patients from Monaco RT session                            | PatientAriaID_RT_year <br> OR <br> PatientAriaID_RT_H_N_Monaco <br> OR <br> PatientAriaID_dateCT_Tmt_IMRT | 3456789_RT_2017 <br> 3456789_RT_H_N_Monaco <br> 3456789_18-07-2012_Tmt_IMRT | CT, RTSS, RTDose, dummy treatment field |


All verification studies were ignored. This was a 2-fold decision based on verification plans being unlikely to be of value in clinical research and the simplicity of recreating them in addition to technical considerations.Verification plans all reference the same CT scan of the verification phantom and identical CTs are not permitted to be stored in multiple locations in XNAT leading to multiple corruptions and conflicts when we attempted to ingest verification plans.
XNAT ingests all available files attached to an imaging session in Aria. This means that all CBCTs for post-Aria patients are attached to the imaging session containing the original planning CT, structure set and dose cube (likely to be the things most of interest to a researcher). This means careful selection of data must take place when giving data to researchers. This is covered in the downloading data from XNAT SOP.
A .csv file detailing the radiotherapy information retrieved and expected in XNAT was produced, this is attached to the RT-HaND_I data lake as a .csv file in XNAT, this also features the descriptions of how many fractions patients received on each plan in the event of replans and any known errors in data retrieval.  
