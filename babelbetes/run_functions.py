# File: run_functions.py
# Author Jan Wrede, Rachel Brandt
# Copyright (c) 2025 nudgebg
# Licensed under the MIT License. See LICENSE file for details.
"""
run_functions.py

This script performs data normalization on raw study data found in the `data/raw` directory.

Execution:
    python run_functions.py

Process Overview:
1. Identifies the appropriate handler class (subclass of studydataset) for each folder in the `data/raw` directory (see supported studies).
2. Loads the study data into memory.
3. Extracts bolus, basal, CGM event histories, and age data into a standardized format (see Output Format).
4. Saves the extracted data as CSV files.

## Output format:
The outptut format is standardized across all studies and follows the definitions of the studydataset base class.

### Boluses

`bolus_history.csv`: Event stream of all bolus delivery events. Standard boluses are assumed to be delivered immediately.

  | Column Name       | Type           | Description                               |
  |-------------------|----------------|-------------------------------------------|
  | patient_id        | str            | Patient ID                                |
  | datetime          | pd.Timestamp   | Datetime of the bolus event               |
  | bolus             | float          | Actual delivered bolus amount in units    |
  | delivery_duration | pd.Timedelta   | Duration of the bolus delivery            |


### Basal Rates

`basal_history.csv: `Event stream of basal rates, accounting for temporary basal adjustments, pump suspends, and closed-loop modes. The basal rates are active until the next rate is reported.

  | Column Name       | Type           | Description                               |
  |-------------------|----------------|-------------------------------------------|
  | patient_id        | str            | Patient ID                                |
  | datetime          | pd.Timestamp   | Datetime of the basal rate start event    |
  | basal_rate        | float          | Basal rate in units per hour              |


### CGM (Continuous Glucose Monitor)

`cgm_history.csv`: Event stream of CGM values.

  | Column Name       | Type           | Description                               |
  |-------------------|----------------|-------------------------------------------|
  | patient_id        | str            | Patient ID                                |
  | datetime          | pd.Timestamp   | Datetime of the CGM measurement           |
  | cgm               | float          | CGM value in mg/dL                        |


### Age Data

`age_data.csv`: Patient age at study enrollment/start.

  | Column Name       | Type           | Description                               |
  |-------------------|----------------|-------------------------------------------|
  | patient_id        | str            | Patient ID                                |
  | age               | float          | Patient age at study enrollment/start    |

### Output Files:
For each study, the dataframes are saved in the `data/out/<study-name>/` folder:
 - To reduce file size, the data is saved in a compressed format using the `gzip`
 - datetimes and timedeltas are saved as unix timestamps (seconds) and integers (seconds) respectively.
 - boluses and basals are rounded to 4 decimal places
 - cgm values are converted to integers

"""
import os
from babelbetes.studies import StudyDataset, dataset_initializer
from babelbetes.pandas_helper import drop_repetitive_basals
from babelbetes.logger import Logger
from babelbetes import data_store
from datetime import datetime
from tqdm import tqdm
import argparse
import importlib.metadata
import json
import subprocess
from time import time

logger = Logger.get_logger(__file__)

def current_time():
  return datetime.now().strftime("%H:%M:%S")

def write_manifest(out_path, study_name, data_types):
  """Record which code produced the output of a study in <out_path>/manifest.json.

  One entry per study and data type with the extraction time, the babelbetes version and
  the git commit, so results computed on the output can be traced back to the code that
  extracted it. dirty is True if the babelbetes package had uncommitted changes; commit
  and dirty are None outside a git checkout.
  """
  def git(*args):
    try:
      return subprocess.run(['git', *args], cwd=os.path.dirname(os.path.abspath(__file__)),
                            capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
      return None

  try:
    version = importlib.metadata.version('babelbetes')
  except importlib.metadata.PackageNotFoundError:
    version = None
  commit = git('rev-parse', '--short', 'HEAD')
  entry = dict(extracted_at=datetime.now().isoformat(timespec='seconds'), version=version,
               commit=commit, dirty=bool(git('status', '--porcelain', '--', '.')) if commit else None)

  path = os.path.join(out_path, 'manifest.json')
  manifest = json.load(open(path)) if os.path.exists(path) else {}
  manifest.update({f'{study_name}/{data_type}': entry for data_type in data_types})
  with open(path, 'w') as f:
    json.dump(manifest, f, indent=2, sort_keys=True)

def main(load_subset=False, remove_repetitive=True, input_dir=None, output_dir=None, studies=None, data_types=None):
  """
  Main function to process study data folders.

  Args:
    load_subset (bool): If True, runs the script on a limited amount of data (e.g. skipping rows).
    input_dir (str): Custom input directory path. Defaults to 'data/raw'.
    output_dir (str): Custom output directory path. Defaults to 'data/out'.
    studies (list): List of study names to process. If None, all available studies will be processed.
                   Available studies: IOBP2, Flair, PEDAP, DCLP3, DCLP5, ReplaceBG, Loop, T1DEXI, T1DEXIP
    data_types (list): List of data types to extract ['cgm', 'bolus', 'basal', 'age']. If None, all types are extracted.
  
  Logs:
    - Information about the current working directory and paths being used.
    - Warnings for folders that do not match any known study patterns.
    - Errors if no supported studies are found.
    - Progress of processing each matched study folder.
  """
  current_dir = os.getcwd()
  in_path = input_dir if input_dir else os.path.join(current_dir, 'data', 'raw')
  out_path = output_dir if output_dir else os.path.join(current_dir, 'data', 'out')

    
  if load_subset:
     logger.warning(f"ATTENTION: --test was provided: Running in test mode using a subset of the data.")

  logger.info(f"Looking for studies in  {in_path}")
  logger.info(f"Output will be saved to {out_path}")
  all_initialized_studies : list[StudyDataset] = dataset_initializer.initialize_datasets(in_path, subset=load_subset)
  
  if studies is not None:
    if not isinstance(studies, list):
      studies = [studies]  # Convert single string to list
    studies_lower = [s.lower() for s in studies]
    matched_studies = {name: study for name, study in all_initialized_studies.items() if name.lower() in studies_lower}
    
    # Check if any requested studies were not found
    #available_studies = set(all_initialized_studies.keys())
    #requested_studies = set(requested_studies)
    missing_studies = set(studies_lower) - set(name.lower() for name in matched_studies.keys())
    
    if missing_studies:
      logger.warning(f"Requested studies not found: {list(missing_studies)}")
      logger.info(f"Available studies: {list(all_initialized_studies.keys())}")
    
    if not matched_studies:
      logger.error("No requested studies were found. Exiting.")
      return
    
    initialized_studies : list[StudyDataset] = list(matched_studies.values())
    logger.info(f"Processing only matched studies: {list(matched_studies.keys())}")
  else:
    initialized_studies = list(all_initialized_studies.values())
    logger.info(f"Processing all available studies: {list(all_initialized_studies.keys())}")
  
  # Validate and process data_types parameter
  available_data_types = ['cgm', 'bolus', 'basal', 'age', 'carbs']
  if data_types is not None:
    if not isinstance(data_types, list):
      data_types = [data_types]  # Convert single string to list
    
    # Validate data types
    invalid_types = [dt for dt in data_types if dt not in available_data_types]
    if invalid_types:
      logger.error(f"Invalid data types: {invalid_types}. Available types: {available_data_types}")
      return
    
    logger.info(f"Processing only requested data types: {data_types}")
  else:
    data_types = available_data_types
    logger.info(f"Processing all data types: {data_types}")

  # Process matched folders with progress indicators
  logger.info(f"Start processing:")

  
  with tqdm(total=len(initialized_studies), desc=f"Processing studies", bar_format='Study {n_fmt}/{total_fmt} [{desc}]:|{bar}', unit="studies", leave=False) as progress:
    global_start_time = time()
    for study in initialized_studies:
      tqdm.write(f"[{current_time()}] {study.study_name} ...")
      
      # Clean up existing output for this study
      removed_paths = data_store.cleanup(study.study_name, out_path, data_types)
      if removed_paths:
        tqdm.write(f"[{current_time()}] Cleaned up existing output: {len(removed_paths)} items removed")

      start_time = time()
      try:
         process_folder(study, out_path, progress, remove_repetitive=remove_repetitive, data_types=data_types)
         write_manifest(out_path, study.study_name, data_types)
      except Exception as e:
          tqdm.write(f"[{current_time()}] Error processing {study.study_name}: {e}")
          logger.error(f"Error processing {study.study_name}: {e} \n" \
                       "Please make sure that you have the supported study dataset release. \n" \
                        "In some cases, newer or older versions of the data are incomtaible. \n" \
                        "Please check the README file for supported study datasets and releases. \n" \
                        "If you continue having issues, we are happy to help.")
          
          
      progress.update(1)
      tqdm.write(f"[{current_time()}] {study.study_name} completed in {time() - start_time:.2f} seconds.")
      study.unload_raw()
    tqdm.write(f"Processing completed in {time() - global_start_time:.2f} seconds.")

def process_folder(study: StudyDataset, out_path: str, progress, remove_repetitive, data_types):
      """Processes the data for a given study by loading, extracting, and saving bolus, basal, CGM, and age events.

        Args:
          study (StudyDataset): Study instance to extract data from.
          out_path (str): Root output directory (e.g. "data/out").
          progress (tqdm): Progress bar to update.
          remove_repetitive (bool): Whether to drop repetitive basal values.
          data_types (list): Data types to extract ['cgm', 'bolus', 'basal', 'age'].
        """
      if 'bolus' in data_types:
          progress.set_description_str(f"{study.__class__.__name__}: Extracting boluses")
          data_store.save(study.bolus, study.study_name, 'bolus', out_path)
          tqdm.write(f"[{current_time()}] [x] Boluses extracted")

      if 'basal' in data_types:
          progress.set_description_str(f"{study.__class__.__name__}: Extracting basals")
          df = study.basal
          if remove_repetitive:
             progress.set_description_str(f"{study.__class__.__name__}: Removing repetitive basals")
             df = df.groupby(StudyDataset.COL_NAME_PATIENT_ID).apply(drop_repetitive_basals, include_groups=False).reset_index(level=0)
          data_store.save(df, study.study_name, 'basal', out_path)
          tqdm.write(f"[{current_time()}] [x] Basal extracted")

      if 'cgm' in data_types:
          progress.set_description_str(f"{study.__class__.__name__}: Extracting glucose")
          data_store.save(study.cgm, study.study_name, 'cgm', out_path)
          tqdm.write(f"[{current_time()}] [x] CGM extracted")

      if 'age' in data_types:
          progress.set_description_str(f"{study.__class__.__name__}: Extracting age data")
          data_store.save(study.age, study.study_name, 'age', out_path)
          tqdm.write(f"[{current_time()}] [x] Age data extracted")

      if 'carbs' in data_types:
          try:
              progress.set_description_str(f"{study.__class__.__name__}: Extracting carbs")
              data_store.save(study.carbs, study.study_name, 'carbs', out_path)
              tqdm.write(f"[{current_time()}] [x] Carbs extracted")
          except NotImplementedError:
              tqdm.write(f"[{current_time()}] [-] Carbs not implemented for {study.study_name}, skipping")
      

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Run data normalization on raw study data.")
  parser.add_argument('--test', action='store_true', help="Run the script in test mode using test data.")
  parser.add_argument('--input-dir', type=str, help="Specify a custom input directory. Defaults to 'data/raw'.")
  parser.add_argument('--output-dir', type=str, help="Specify a custom output directory. Defaults to 'data/out'.")
  parser.add_argument('--remove-repetitive', action='store_true', help="Remove repetitive values from the basal output dataframes.")
  parser.add_argument('--studies', nargs='*', help="Specify which studies to process. Available: IOBP2, Flair, PEDAP, DCLP3, DCLP5, ReplaceBG, Loop, T1DEXI, T1DEXIP. If not specified, all available studies will be processed.")
  parser.add_argument('--data-types', nargs='*', choices=['cgm', 'bolus', 'basal', 'age', 'carbs'], help="Specify which data types to extract. Available: cgm, bolus, basal, age, carbs. If not specified, all data types will be extracted.")
  args = parser.parse_args()

  logger.info(f"Using arguments:")
  for arg, value in vars(args).items():
      logger.info(f"  {arg}: {value}")
  main(load_subset=args.test, remove_repetitive=args.remove_repetitive, input_dir=args.input_dir, output_dir=args.output_dir, studies=args.studies, data_types=args.data_types)