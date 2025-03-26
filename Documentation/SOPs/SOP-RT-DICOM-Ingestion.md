# RT DICOM Ingestion from ARIA

The XNAT data lake will be updated with radiotherapy DICOM data on a 3-monthly basis for two streams of ingestion:

- Ingestion of data for new patients
- Ongoing ingestion of data for existing patients

Ingestion for both streams will follow a similar process:

### Step 1. Query ARIA for associated studies
To update the XNAT repository, ARIA should be queried for studies associated with each patient ID.
- For new patients, ARIA should be queried for ALL studies
- For ongoing ingestion, ARIA should be queried for studies within a specified date range (e.g. 3 month date range, since the previous ingestion)

Collation of patient lists will be carried out by the project administrator and provided to the CSC team.  The CSC team will return to the administrator the following fields for available data in ARIA:


| patientId| studyInstanceUID | studyId| accessionNumber| studyDate| studyDescription|
|-         |-                 |-       |-               |-         |-                |

The studies listed in this table will most likely consist of radiotherapy planning CT scans to which other DICOM objects are attached, and other pre-treatment imaging such as MRI and PET-CT scans.  There may also be studies such as orthovoltage and electron treatments.  The radiotherapy planning CT scans do not have accession numbers associated with them, whereas other imaging studies do.

### Step 2. Remove Irrelevant Studies
Some of the studies found in the ARIA query will not need to be ingested into XNAT, including verification studies.  Attempting to ingest verification studies causes complications in the ingestion process.  Therefore, these studies should be removed by searching for any Study Instance UIDs which start with the following sequence and removing these entries:

|Study Instance UID prefixes for verification plans|
|-                            |
|1.2.246.352.71.1.658820455611|
|1.2.246.352.71.1.850931706547|

### Step 3. Assign Study Descriptions
From the table provided by the ARIA query, the Study Description field will be blank.  Each study must be labeled with a unique name before it is ingested into XNAT.  Ideally studies will be labelled as in the table below:



| RT session type examples                                      | Labelling convention                                      | Example                                      | Data element examples (“scans”) stored as DICOM files |
|--------------------------------------------------------------|----------------------------------------------------------|----------------------------------------------|------------------------------------------------------|
| Pre-treatment imaging                                        | PatientAriaID_RT_year_AccessionNumber                    | 3456789_RT_2017_RJxxxxxxxxxx               | Diagnostic MRI or CT or PET-CT scans, regs.          |
| RT session                                                  | PatientAriaID_RT_year                                    | 3456789_RT_2017                            | CT, RTSS, RTDose, RTPlan and for post Aria patients; CBCTs, CBCT SS and regs and RTRecords. |
| RT session replan                                           | PatientAriaID_RT_year_REPLAN/RESCAN                      | 3456789_RT_2017_REPLAN                     | CT, RTSS, RTDose, RTPlan, reg, CBCTs, CBCT SS and regs and RTRecords. |
| RT session (multiple within 1 year e.g. palliative mets)    | PatientAriaID_RT_year_BodyPartTreated                    | 3456789_RT_2017_SPINE <br> 3456789_RT_2017_WHOLEBRAIN | CT, RTSS, RTDose, RTPlan |
| On-treatment CBCT (pre-Aria)                                | PatientAriaID_RT_year_CBCT                               | 3456789_RT_2017_CBCT                       | CBCT scan, reg, RTSS |
| Patients from Monaco RT session                            | PatientAriaID_RT_year <br> OR <br> PatientAriaID_RT_H_N_Monaco <br> OR <br> PatientAriaID_dateCT_Tmt_IMRT | 3456789_RT_2017 <br> 3456789_RT_H_N_Monaco <br> 3456789_18-07-2012_Tmt_IMRT | CT, RTSS, RTDose, dummy treatment field |

|Abbreviation|Definition|
|-|-|
|CT|Radiotherapy planning CT| 
|RTSS|Radiotherapy structure set|
|RTDose|RT dosecube file| 
|RTPlan|RT plan file| 
|reg|registrations to planning CT| 
|CBCT SS|Structure set associated with CBCT| 
|RTRecords|Beam delivery records produced by ARIA|  

However, this is a time consuming process and not practical when there is a large amount of data to be ingested and limited time to work with.  A simpler method to produce unique descriptions is to using the following labelling:
| RT session type examples                                     | Labelling convention                                    | Example                                    |
|--------------------------------------------------------------|---------------------------------------------------------|--------------------------------------------|
|Pre-treatment imaging                                         | PatientAriaID_RT_year_AccessionNumber                   | 3456789_RT_2025_APLxxxxxxxxx               |
|RT Session                                                    | PatientAriaID_RT_year_StudyID                           |3456789_RT_2025_98765                       |

This can be achieved with the following excel formula:
```
=patientId&"_RT_"&YEAR(studyDate)&"_"&IF(accessionNumber<>"",accessionNumber,studyId)
```

Once all studies have been labelled, the table should be checked to ensure there are no duplicates.  If duplicates are found, the UIDs/ARIA should be checked to determine whether they are two separate studies, in which case the most recent should be appended with a number, and if they are the same study, one of the rows should be removed.

### Step 4. Associate ARIA MRN with NHS ID
Data pulled from ARIA will only be associated with the ARIA MRN, whereas the XNAT data lake is identified through NHS ID.  In order to ingest from ARIA, studies must be linked to an NHS ID.  An additional column must be added to the table.  A VLOOKUP formula can be used alongside the master patient list to complete this column. 

Finally, the sheet should be sent to the CSC team as a .csv file.

### Step 5. Manage Failed Ingestions
Following ingestion of the studies into XNAT, there may be some failures. These will need to be assessed on a case-by-case basis.  Possible methods of dealing with failures are to attempt re-ingestion 

****CONTINUE HERE******

XNAT ingests all available files attached to an imaging session in Aria. This means that all CBCTs for post-Aria patients are attached to the imaging session containing the original planning CT, structure set and dose cube (likely to be the things most of interest to a researcher). This means careful selection of data must take place when giving data to researchers. This is covered in the downloading data from XNAT SOP.
A .csv file detailing the radiotherapy information retrieved and expected in XNAT was produced, this is attached to the RT-HaND_I data lake as a .csv file in XNAT, this also features the descriptions of how many fractions patients received on each plan in the event of replans and any known errors in data retrieval.  
