## Table of Contents
1. [Introduction](#introduction)
2. [Team Members](#team-members)
3. [Files](#files)
4. [Publications](#publications)
6. [Roadmap](#roadmap)
7. [Acknowledgements](#acknowledgements)

## Introduction
RT-HaND is a large, clinically annotated imaging data lake of Head and Neck Cancer patients.  

The complete HNC data lake (RT-HaND) is composed of the XNAT data lake (RT-HaND_I) (containing imaging and radiotherapy DICOM data) plus a set of (currently) 157 tables in EDW (Enterprise Data Warehouse) (RT-HaND_C) which contain over 7 million clinical data points.

RT-HaND_C comprises of demographic, disease, treatment and outcome data from 2895 patients seen by the GSTT Head and Neck Oncology team between 1/1/2010 and 4/10/2023. Data is up-to-date (e.g. follow-up dates) to the point of 4/10/2023.  Originally this data was planned for storage within forms in XNAT, however, initial work demonstrated these are cumbersome to work with and reduce the interoperability of data. Following review of different options EDW was chosen as the preferred method to store non-imaging clinical data. An advantage is that EDW can ingest data and update itself by “hoovering up” spreadsheets in a set location. This enables a team member to keep the database up to date without the involvement of CSC or access to EDW. Clinical data has been sourced from existing tables in EDW, some unstructured data from Mosaiq obtained using CogStack and manual curation.

XNAT is an open-source software that enables ingestion, storage, anonymisation and export of DICOM files. XNAT hosts the imaging and radiotherapy data of the 2895 patients (RT-HaND_I) containing imaging data from diagnosis, treatment and follow-up and all radiotherapy data since the introduction of Intensity Modulated Radiotherapy to the Trust (March 2011). XNAT is hosted in the Trust by the Clinical Scientific Computing (CSC-XNAT) and within this infrastructure, a specific project contains the HNC unanonymised data lake which enables continuous updating of the data. In addition, the Radiotherapy Physics department hosts a separate instance of XNAT (RT-XNAT) designed to uniquely contain anonymised data and cleaned copies of HNC projects. This is linked to CSC-XNAT through opened firewalls and ports enabling data to be sent between the two XNAT instances. The role of RT-XNAT is to enable reusability of data, accessibility of project data (e.g. if asked to reproduce published results) and ensure adherence to data protection principles and information governance.  

## Team Members
**Project Lead:** Teresa Guerrero Urbano  
**Radiotherapy Physics:** Eleanor Ivy & Victoria Butterworth  
**Oncology:** Tom Young  
**Clinical Scientific Computing:** Dijana Vilic & Haleema Drake  

## Files
Documentation relating to the creation of RT-HaND (up until to December 2024) can be found under [Reference Docs](Documentation/Reference%20Docs).

Useful scripts are stored in [Scripts](Scripts)

SOPs for ongoing ingestion into RT-HaND are found under [SOPs](Documentation/SOPs) 

## Publications
https://www.medrxiv.org/content/10.1101/2025.02.12.25322092v1

https://www.thegreenjournal.com/article/S0167-8140(24)02911-6/abstract

## Roadmap
RT-HaND currently holds data for 2895 patients, collected between 01/01/2010 and 04/10/2023.  The switchover to a new patient information system, EPIC, and the move from Mosaiq to a different oncology information system (ARIA), present new hurdles which have slowed the growth of the data lake.  

The current priorities of the project are to create direct links between the EDW database and both EPIC and AURA (the ARIA database).

Alongside this work, XNAT will be updated on a quarterly basis with imaging DICOM and radiotherapy DICOM studies.

Work to smooth out the process of distributing anonymised data to prospective researchers is in progress.

## Acknowledgements
_Last updated: 11/11/2024_
### Names to be included for publications/acknowledgements for researchers using the clinical dataset:

**Any data:**
Teresa Guerrero Urbano, Tom Young, Victoria Butterworth, Eleanor Ivy, Haleema Drake, Dika Vilic, Delali Adjogatse, Imran Petkar, Mary Lei, Anthony Kong, Miguel Reis-Ferreira

**RT imaging data:**
Isabel Palmer, Tania Avgoulea, Josh Andriolo, Carole Creppy and Corla Routledge

**PD-L1 data:**
Lisette Collins

**Oropharynx data:**
Francesca de Felice, Tom Bird

**Oral Cavity data:**
Khrishanthne Sambasivan

### Acknowledgements:

We would like to extend our gratitude to the patients whose data facilitated this evaluative study. We would like to acknowledge the Topol Fellowship Funding from NHS Digital, which helped fund this project. This work was supported by the Radiation Research Unit at the Cancer Research UK City of London Centre Award [C7893/A28990] and by Wilson + Olegario Philanthropy.

We would like to also thank Bill Dann and Aga Giemza from the Mosaiq (Cancer Information System) for their help in providing support with accessing data from Mosaiq for this project.


