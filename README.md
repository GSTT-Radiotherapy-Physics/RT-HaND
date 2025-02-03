## Table of Contents
1. [Introduction](#introduction)
2. [Team Members](#team%20members)
3. [Getting Started](#getting%20started)
4. [Overview](#overview)
5. [Publications](#publications)
6. [Resources](#resources)
7. [Roadmap](#roadmap)
8. [Acknowledgements](#acknowledgements)

## Introduction
RT-HaND is a large clinically annotated imaging data lake of Head and Neck Cancer patients.  

The complete HNC data lake (RT-HaND) is composed of the XNAT data lake (RT-HaND_I) (containing imaging and radiotherapy DICOM data) plus a set of (currently) 157 tables in EDW (Enterprise Data Warehouse) (RT-HaND_C) which contain over 7 million clinical data points.

RT-HaND_C comprises of demographic, disease, treatment and outcome data from 2895 patients seen by the GSTT Head and Neck Oncology team between 1/1/2010 and 4/10/2023. Data is up-to-date (e.g. follow-up dates) to the point of 4/10/2023.  Originally this data was planned for storage within forms in XNAT, however, initial work demonstrated these are cumbersome to work with and reduce the interoperability of data. Following review of different options EDW was chosen as the preferred method to store non-imaging clinical data. An advantage is that EDW can ingest data and update itself by “hoovering up” spreadsheets in a set location. This enables a team member to keep the database up to date without the involvement of CSC or access to EDW. Clinical data has been sourced from existing tables in EDW, some unstructured data from Mosaiq obtained using CogStack and manual curation.

XNAT is an open-source software that enables ingestion, storage, anonymisation and export of DICOM files. XNAT hosts the imaging and radiotherapy data of the 2895 patients (RT-HaND_I) containing imaging data from diagnosis, treatment and follow-up and all radiotherapy data since the introduction of Intensity Modulated Radiotherapy to the Trust (March 2011). XNAT is hosted in the Trust by the Clinical Scientific Computing (CSC-XNAT) and within this infrastructure, a specific project contains the HNC unanonymised data lake which enables continuous updating of the data. In addition, the Radiotherapy Physics department hosts a separate instance of XNAT (RT-XNAT) designed to uniquely contain anonymised data and cleaned copies of HNC projects. This is linked to CSC-XNAT through opened firewalls and ports enabling data to be sent between the two XNAT instances. The role of RT-XNAT is to enable reusability of data, accessibility of project data (e.g. if asked to reproduce published results) and ensure adherence to data protection principles and information governance.   

## Team Members
**Project Lead:** Teresa Guerrero Urbano  
**Radiotherapy Physics:** Eleanor Ivy & Victoria Butterworth  
**Oncology:** Tom Young  
**Clinical Scientific Computing:** Dijana Vilic & Haleema Drake  

Include contact details?

## Getting Started
RT-HaND Staff ...  
Researchers ...

## Overview
## Publications
Link publications here  
## Resources
Links to SOPs

## Roadmap
Going forward
## Acknowledgements
