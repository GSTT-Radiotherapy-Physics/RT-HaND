import pandas as pd
import re
# Step 1: Give link to textfile of json spit out of PACS failures.
file_path = 'PACs-failures.txt'  # Replace with the actual path to your text file
with open(file_path, 'r') as file:
    data = file.read()
# Step 2: Clean the data by fixing quotes and ensuring proper spacing
# Normalize the data by fixing inconsistent double quotes, spaces, and any potential newline issues
normalized_data = re.sub(r'""', '"', data)  # Fix double quotes if present
normalized_data = re.sub(r'\s+', ' ', normalized_data)  # Replace multiple spaces and newlines with single spaces
normalized_data = re.sub(r'"\s*"', '""', normalized_data)  # Ensure there are no empty quotes with spaces in between
#testing demonstrated that by normalising twice the data was then in a pattern searching format.
# Normalize the data by fixing inconsistent double quotes, spaces, and any potential newline issues
normalized_data = re.sub(r'""', '"', normalized_data)  # Fix double quotes if present
normalized_data = re.sub(r'\s+', ' ', normalized_data)  # Replace multiple spaces and newlines with single spaces
normalized_data = re.sub(r'"\s*"', '""', normalized_data)  # Ensure there are no empty quotes with spaces in between
H
# Print normalized data for debugging purposes (optional)
print("Normalized Data:")
print(normalized_data)

# Step 3: Pattern matching. Use regex to capture relevant fields (accessionNumber, id, studyDate, etc.)
pattern = re.compile(
    r'"accessionNumber":\s*"([^"]+)"\s*'  # Capture accessionNumber
    r'"id":\s*"([^"]+)"\s*'               # Capture id
    r'"studyDate":\s*"([^"]+)"\s*'        # Capture studyDate
    r'"studyDescription":\s*"([^"]+)"\s*' # Capture studyDescription
    r'"studyInstanceUid":\s*"([^"]+)"',   # Capture studyInstanceUid
    re.DOTALL
)

# Step 4: Find all matches
matches = pattern.findall(normalized_data)

# Print matches for debugging purposes (optional)
print("Matches Found:")
print(matches)

# Step 5: Create a DataFrame from the extracted matches
df = pd.DataFrame(matches, columns=["AccessionNumber", "ID", "StudyDate", "StudyDescription", "StudyInstanceUid"])
#rearrange data frame to be in the same order as .csv files downloaded from XNAT
df = df[["ID", "StudyDate", "AccessionNumber", "StudyDescription", "StudyInstanceUid"]]
# Display the DataFrame
print("DataFrame:")
print(df)
# Save the DataFrame to a new CSV file
df.to_csv('PACs-non-ingested.csv', index=False)
df_pacs = pd.read_csv('pacs-non-ingested.csv')
#The code can be truncated here if new ingestions contain NHS numbers already. The next section converts between HospitalIDs and NHS numbers.

# Load the HospitalID-NHSNumber spreadsheet containing the old and new IDs
df_ids = pd.read_csv('HospitalID-NHSNumber.csv')

# Merge the dataframes based on the matching IDs ('ID' in pacs-non-ingested with 'HospitalID' in HospitalID-NHSNumber)
df_merged = pd.merge(df_pacs, df_ids[['HospitalID', 'NHSNumber']], left_on='ID', right_on='HospitalID', how='left')

# Replace the old 'ID' with the new 'NHSNumber' and rename the column to 'Subject'
df_merged['ID'] = df_merged['NHSNumber']
df_merged = df_merged.drop(columns=['HospitalID', 'NHSNumber'])  # Drop the unnecessary columns
#rename ID to be subject in line with csvs downloaded from XNAT
df_merged = df_merged.rename(columns={'ID': 'Subject'})

# Save the updated data to a new CSV file
df_merged.to_csv('pacs-non-ingested.csv', index=False)
#Either combine the .txt files of non-ingested PACS data from previous iterations of ingestions OR combine the .csvs before adding to XNATImagingSummary otherwise we will lose details of previous failed ingestions.
