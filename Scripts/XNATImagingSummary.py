import pandas as pd

# Function to sort, expand, and calculate the difference from the provided date
def sort_and_expand(df, reference_dates_df, scan_type):
    # Extract columns by position, assuming the structure you provided
    df.columns = ['Subject', 'Date', 'ID', 'UID', 'Scans']  # Generic column names for consistent access
    reference_dates_df.columns = ['Subject', 'Reference Date']  # Columns for the new spreadsheet
    df = df[df['Subject'].notna() & (df['Subject'] != '')]
    # Merge the scan data with the reference dates based on 'Subject'
    df = df.merge(reference_dates_df, on='Subject', how='left')
    # Exclude any rows where Subject is "nan"
    df = df[df['Subject'].notna() & (df['Subject'] != '')]
    # Convert both 'Date' and 'Reference Date' to datetime for proper calculations
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Reference Date'] = pd.to_datetime(df['Reference Date'], errors='coerce')

    # **Exclude any rows where the 'Date' is 01-01-2099**
    df = df[df['Date'] != pd.Timestamp('2099-01-01')]
    #bin off blank subjects or nan
    df = df[df['Subject'].notna() & (df['Subject'] != 'nan')]
    # Group by 'Subject'
    grouped = df.groupby('Subject')

    expanded_rows = []

    # Iterate over each subject and their corresponding rows
    for subject, group in grouped:
        # Get the reference date for the subject
        reference_date = group['Reference Date'].iloc[0]

        # Sort the rows by 'Date', placing rows with missing dates at the end
        group = group.sort_values(by='Date', key=lambda x: pd.to_datetime(x, errors='coerce')).reset_index(drop=True)

        # Collect sorted data
        sorted_dates = group['Date'].tolist()
        sorted_ids = group['ID'].tolist()
        sorted_uids = group['UID'].tolist()
        sorted_scans = group['Scans'].tolist()

        # Create a dictionary for the expanded columns
        expanded_row = {'Subject': subject}

        # Add Reference Date or "not applicable" if missing
        if pd.notna(reference_date):
            expanded_row['Reference Date'] = reference_date.strftime('%Y-%m-%d')
        else:
            expanded_row['Reference Date'] = "not applicable"

        # Expand columns for each scan (numbering them sequentially)
        for i in range(len(sorted_dates)):
            # Date column
            date_value = sorted_dates[i].strftime('%Y-%m-%d') if pd.notna(sorted_dates[i]) else "null"
            expanded_row[f'{scan_type} Date {i + 1}'] = date_value

            # Difference from reference date, or "not applicable" if no reference date
            if pd.notna(sorted_dates[i]) and pd.notna(reference_date):
                difference = (sorted_dates[i] - reference_date).days
            elif pd.notna(sorted_dates[i]) and not pd.notna(reference_date):
                difference = "not applicable"
            else:
                difference = "null"

            expanded_row[f'{scan_type} Difference from Reference Date {i + 1}'] = difference

            # For ID, UID, and Scans, replace missing values with "null"
            expanded_row[f'{scan_type} ID {i + 1}'] = sorted_ids[i] if pd.notna(sorted_ids[i]) else "null"
            expanded_row[f'{scan_type} UID {i + 1}'] = sorted_uids[i] if pd.notna(sorted_uids[i]) else "null"
            expanded_row[f'{scan_type} Scans {i + 1}'] = sorted_scans[i] if pd.notna(sorted_scans[i]) else "null"

        # Check for missing scans, ensuring that all columns are present for each scan type
        max_scans = len(sorted_dates)
        num_columns_to_fill = 5  # Corresponding to Date, Difference, ID, UID, Scans
        while max_scans < num_columns_to_fill:
            max_scans += 1
            expanded_row[f'{scan_type} Date {max_scans}'] = "null"
            expanded_row[f'{scan_type} Difference from Reference Date {max_scans}'] = "null"
            expanded_row[f'{scan_type} ID {max_scans}'] = "null"
            expanded_row[f'{scan_type} UID {max_scans}'] = "null"
            expanded_row[f'{scan_type} Scans {max_scans}'] = "null"

        expanded_rows.append(expanded_row)

    # Convert the list of expanded rows back into a DataFrame
    expanded_df = pd.DataFrame(expanded_rows)

    return expanded_df
# Load the original data for all scan types e.g. 8 .csvs plus the PACS-not-ingested csv from PACSIngestionError script.
scan_types = ['CT', 'MR', 'PET', 'CR', 'DX', 'RF', 'SR', 'XA', 'PACs-not-ingested']
#Assumes scans are saved in location with date in title, edit below as required.
dataframes = {scan_type: pd.read_csv(f'300924/{scan_type}.csv') for scan_type in scan_types}

# Ensure 'Subject' columns are of type string
for scan_type in scan_types:
    dataframes[scan_type]['Subject'] = dataframes[scan_type]['Subject'].astype(str)

# Load the reference dates file
#Again assumes within a dated folder, edit accordingly
reference_dates = pd.read_csv('300924/reference_dates.csv')  # This contains Subject and Reference Date columns
reference_dates['Subject'] = reference_dates['Subject'].astype(str)  # Ensure Subject is string

# Sort and expand the data for all scan types using the reference dates
expanded_dataframes = {scan_type: sort_and_expand(dataframes[scan_type], reference_dates, scan_type) for scan_type in
                       scan_types}

# Merge all expanded datasets on the 'Subject' column
merged_data = expanded_dataframes['CT']
for scan_type in scan_types[1:]:
    merged_data = merged_data.merge(expanded_dataframes[scan_type], on='Subject', how='outer')

# Replace missing values with "null" in the entire merged dataset
merged_data = merged_data.fillna('null')

# Save the final merged and sorted data to a new CSV file
merged_data.to_csv('final_sorted_merged_scans_with_nulls_no2099.csv', index=False)

# Print the first few rows of the merged data
print(merged_data.head())
