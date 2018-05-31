#!/usr/bin/env python3
# coding: utf-8

# Converters from search-engine inputs to compatible outputs
# for alignment and update

import argparse
import logging
import numpy as np
import os
import pandas as pd
import pkg_resources
import re
import sys
import yaml

from functools import reduce
from rtlib.helper import *

logger = logging.getLogger("root")

# all filter funcs take in the df_original, df, config object, and the filter object
# as inputs, and output the exclude vector (True/False), where True means
# to exclude that particular row

def filter_uniprot_exclusion_list(df_original, df, config, _filter):
  """
  Filter proteins from exclusion list using UniProt IDs
  """

  exclusion_list = []

  # parse exclusion list
  # if exclusion_list param is a path, then load the IDs from that path
  if "file" in _filter and _filter["file"] is not None:
    # load UniProt IDs from file line-by-line
    # first expand user or any vars
    _filter["file"] = os.path.expanduser(_filter["file"])
    _filter["file"] = os.path.expandvars(_filter["file"])

    # open the exclusion list file and read in the UniProt IDs, line by line
    try:
      with open(_filter["file"], "r") as f:
        logger.info("Loading UniProt IDs from exclusion list file {} ...".format(_filter["file"]))
        exclusion_list = [line.rstrip('\n') for line in f]
        logger.info("Loaded {} proteins from exclusion list.".format(len(exclusion_list)))
    except EnvironmentError:
      logger.warning("Exclusion list file {} not found. Skipping UniProt ID exclusion list filter.".format(_filter["file"]))
      return None

  elif "list" in _filter and len(_filter["list"]) > 0:
    # load UniProt IDs from the configuration file
    exclusion_list = _filter["list"]
    logger.info("Loading {} UniProt IDs from exclusion list as defined in config file".format(len(exclusion_list)))
  else:
    logger.warning("No exclusion list file or list of UniProt IDs provided. Skipping UniProt ID exclusion list filter.")
    return None

  # filter exclusion list
  if len(exclusion_list) > 0:
    logger.info("UniProt IDs from exclusion list: {}".format(exclusion_list))

    # we could only match the excluded IDs to the razor protein,
    # but we can be more strict and match the blacklisted IDs to the entire protein
    # string, containing all possible proteins
    pat = reduce((lambda x, y: x + "|" + y), exclusion_list)
    blacklist_filter = df["proteins"].str.contains(pat)
    blacklist_filter[pd.isnull(blacklist_filter)] = False

    logger.info("Filtering out {} PSMs from the exclusion list".format(np.sum(blacklist_filter)))
    return blacklist_filter
  else:
    logger.warning("Exclusion list found and loaded, but no UniProt IDs found. Check the format of the file, or the list in the config file. Skipping UniProt ID exclusion list filter.")
    return None

def filter_contaminant(df_original, df, config, _filter):
  """
  Filter contaminants, as marked by the search engine
  Looking for a contaminant tag in the leading_protein column
  """

  # load the tag in from the config file
  CON_TAG = _filter["tag"]
  # search for the tag in the "proteins" column
  filter_con = df["proteins"].str.contains(CON_TAG)
  filter_con[pd.isnull(filter_con)] = False

  logger.info("Filtering out {} PSMs as contaminants with tag \"{}\"".format(np.sum(filter_con), CON_TAG))
  return filter_con

def filter_decoy(df_original, df, config, _filter):
  """
  Filter decoys, as marked by the search engine
  Looking for a decoy tag in the leading_protein column
  """

  # load the tag in from the config file
  REV_TAG = _filter["tag"]
  # search for the tag in the "leading protein" column
  filter_rev = df["leading_protein"].str.contains(REV_TAG)
  filter_rev[pd.isnull(filter_rev)] = False

  logger.info("Filtering out {} PSMs as decoys with tag \"{}\"".format(np.sum(filter_rev), REV_TAG))
  return filter_rev

def filter_retention_length(df_original, df, config, _filter):
  """
  Filter by retention length, which is a measure of the peak width
  during chromatography.
  """

  # input checks
  if "value" not in _filter or _filter["value"] is None:
    logger.warning("No value provided to the retention_length filter. Skipping this filter.")
    return None
  if "dynamic" not in _filter or type(_filter["dynamic"]) is not bool:
    logger.warning("Incorrect value provided to the \"dynamic\" field of the retention_length filter. Please provide a bool, either true or false. Skipping this filter.")
    return None
  
  if _filter["dynamic"]:
    # use the dynamic filter, where the value is a proportion
    # of the max RT (the run-time) of that raw file
    
    # only allow values between 0 and 1 for the dynamic filter
    if _filter["value"] > 1 or _filter["value"] <= 0:
      logger.warning("Dynamic retention_length filter {} is above 1 or below 0. Please provide a number between 0 and 1, which is the fraction of the max RT for each experiment. e.g., 0.01 means that 1%% of the max RT will be used as the retention_length threshold.".format(_filter["value"]))
      return None

    logger.info("Using dynamic retention length of {} * run-time (max RT) for each experiment".format(_filter["value"]))

    # get the max RT for each raw file, reindex to the same dimension as the
    # retention_length column, and then multiply by the filter value
    max_rts = df.groupby("exp_id")["retention_time"].max().values
    filter_rtl = max_rts[df["exp_id"]] * _filter["value"]

    filter_rtl = (df["retention_length"] > filter_rtl)

  else:
    # use a constant filter for the retention length
    logger.info("Using constant retention length (in RT) of {} for all raw files.".format(_filter["value"]))

    # only allow values between 0 and max(RT)
    if _filter["value"] <= 0 or _filter["value"] > np.max(df["retention_time"]):
      logger.warning("retention_length filter {} is not defined or incorrectly defined. Please provide a decimal number between 0.0 and max(RT).".format(_filter["value"]))
      return None
    
    filter_rtl = (df["retention_length"] > _filter["value"])

  if _filter["dynamic"]:
    logger.info("Filtering out {} PSMs with retention length greater than {:.2f} * max(exp_RT) of each raw file.".format(np.sum(filter_rtl), _filter["value"]))
  else:
    logger.info("Filtering out {} PSMs with retention length greater than {:.2f}".format(np.sum(filter_rtl), _filter["value"]))
  return filter_rtl

def filter_pep(df_original, df, config, _filter):
  """
  Filter by PEP (Posterior Error Probability), 
  measured from spectra and a search engine
  """

  # input checking
  if "value" not in _filter or _filter["value"] is None:
    logger.warning("PEP filter not defined. Skipping PEP filter...")
    return None

  # only allow values between 0 and 1
  if _filter["value"] <= 0 or _filter["value"] > 1:
    logger.warning("PEP filter {} is not defined or incorrectly defined. Please provide a decimal number between 0.0 and 1.0. Skipping PEP filter...".format(_filter["value"]))
    return None

  filter_pep = (df["pep"] > _filter["value"])

  logger.info("Filtering out {} PSMs with PEP greater than {:.2f}".format(np.sum(filter_pep), _filter["value"]))
  return filter_pep

def filter_num_exps(df_original, df, config, _filter):
  """
  Filter for occurence of PSM in number of experiments
  i.e., filter out all PSMs of peptide, if that peptide has only been 
  observed in less than n experiments
  """

  # input checking
  if "value" not in _filter or _filter["value"] is None or _filter["value"] < 1:
    logger.warning("Incorrect value provided to the filter for the number of raw files that a peptide must be observed in. Please provide a value greater than or equal to 1. Skipping this filter.")
    return None
  if _filter["value"] == 1:
    logger.warning("Filter for number of raw files that a peptide must be observed in is set to 1. The alignment will proceed but this may result in non-informative canonical RTs and high residuals. It is recommended that this parameter is at least 3.")

  # only want to do this operation on PSMs that aren't already marked to be filtered out
  # first, take subset on remaining PSMs, then count number 
  # of unique experiments for each of them
  exps_per_pep = df[-(df["exclude"])].groupby("peptide_id")["exp_id"].unique().apply((lambda x: len(x)))
  # map values to DataFrame. peptides without any value will get NaN,
  # which will then be assigned to 0.
  exps_per_pep = df["peptide_id"].map(exps_per_pep)
  exps_per_pep[np.isnan(exps_per_pep)] = 0

  filter_n_exps = (exps_per_pep < _filter["value"])

  logger.info("Filtering out {} PSMs that have less than {} occurrences in different experiments.".format(filter_n_exps.sum(), _filter["value"]))
  return filter_n_exps

def filter_smears(df_original, df, config, _filter):
  """
  Filter out "smears". even confidently identified PSMs can have bad chromatography,
  and in that case it is unproductive to include them into the alignment.
  In theory, this should be made redundant by the retention length filter, but
  some PSMs still slip through the cracks of that, possibly because the search engine
  cannot adequately track the elution peak?
  """

  # input checking
  if "value" not in _filter or _filter["value"] is None:
    logger.warning("No value provided to the smears filter. Skipping this filter.")
    return None
  if "dynamic" not in _filter or type(_filter["dynamic"]) is not bool:
    logger.warning("Incorrect value provided to the \"dynamic\" field of the smears filter. Please provide a bool, either true or false. Skipping this filter.")
    return None

  # TODO: there might also be merit to excluding these observations from the PEP update
  # process as well, given that the spectral PEP is below a very 
  # conservative threshold (1% or maybe even lower)
  logger.info("Determining RT spread of peptides within each experiment...")
  # for each experiment-peptide pair, get the range of retention times
  # this is the step that could take a long time
  # TODO: optimize this?
  smears = df.groupby(["exp_id", "peptide_id"])["retention_time"].apply(np.ptp)
  
  if _filter["dynamic"]:
    # use the dynamic filter, where the value is a proportion
    # of the max RT (the run-time) of that raw file
    
    if _filter["value"] > 1 or _filter["value"] <= 0:
      logger.warning("Dynamic smear filter {} is above 1 or below 0. Please provide a number between 0 and 1, which is the fraction of the max RT for each experiment. e.g., 0.01 means that 1%% of the max RT will be used as the smear threshold.".format(_filter["value"]))
      return None

    logger.info("Using dynamic smear length (in RT) of {} * run-time (max RT) for each experiment".format(_filter["value"]))

    max_rts = df.groupby("exp_id")["retention_time"].max().values

    # get the (exp_id, peptide_id) tuples for PSMs with a range above the threshold
    smears = smears[smears > max_rts[smears.index.to_frame()["exp_id"].values] * _filter["value"]].index.values

  else:
    # use a constant filter for the retention length
    logger.info("Using constant smear length (in RT) of {} for all raw files.".format(_filter["value"]))

    if _filter["value"] <= 0:
      logger.warning("smear filter {} is not defined or incorrectly defined. Please provide a decimal number between 0.0 and max(RT).".format(filter_retention_length))
      return None

    # get the (exp_id, peptide_id) tuples for PSMs with a range above the threshold
    smears = smears[smears > _filter["value"]].index.values
  
  # map the tuples back to the original data frame, and set smears to be excluded
  smears = pd.Series(list(zip(df["exp_id"], df["peptide_id"]))).isin(smears)

  if _filter["dynamic"]:
    logger.info("Filtering out {} PSMs with an intra-experiment RT spread greater than {} * max(exp_RT) for each raw file.".format(smears.sum(), _filter["value"]))
  else:
    logger.info("Filtering out {} PSMs with an intra-experiment RT spread greater than {}".format(smears.sum(), _filter["value"]))

  return smears

# dictionary of all filter functions
filter_funcs = {
  "uniprot_exclusion":  filter_uniprot_exclusion_list,
  "contaminant":        filter_contaminant,
  "decoy":              filter_decoy,
  "retention_length":   filter_retention_length,
  "pep":                filter_pep,
  "num_exps":           filter_num_exps,
  "smears":             filter_smears
}

# columns required for each filter to run
# will skip the filter if this column does not exist in the input file
required_cols = {
  "uniprot_exclusion":  ["proteins"],
  "contaminant":        ["proteins"],
  "decoy":              ["leading_protein"],
  "retention_length":   ["retention_length"],
  "pep":                [],
  "num_exps":           [],
  "smears":             []
}


def convert(df, config):
  # use canonical sequence, or modified sequence?
  seq_column = "sequence"
  # make sure the modified sequence column exists as well
  if not config["use_unmodified_sequence"]:
    if type(config["col_names"]["modified_sequence"]) is str:
      seq_column = "modified_sequence"
    else:
      raise Exception("Modified Sequence selected but either input file type does not support modified sequences, or the input file type is missing the modified sequence column.")
  else:
    logger.info("Using unmodified peptide sequence instead of modified peptide sequence")

  # load the sequence column first
  cols = [config["col_names"][seq_column]]
  col_names = ["sequence"]
  # loop thru all columns listed in the config file
  for col in list(config["col_names"].keys()):
    # don't add this column if its the sequence column, or if
    # it's not specified
    if col in ["sequence", "modified_sequence"]: continue
    if config["col_names"][col] is None: 
      logger.info("Column \"{}\" is left empty in the config file. Skipping...".format(col))
      continue

    # check if the column specified in the config file exists in the df or not
    if config["col_names"][col] not in df.columns:
      # this is probably grounds to kill the program
      raise Exception("Column {} of value {} not found in the input file. Please check that this column exists, or leave the field for {} empty in the config file.".format(col, config["col_names"][col], col))

    # keep track of the column and the column name
    cols.append(config["col_names"][col])
    col_names.append(col)

  # take the subset of the input file, and also rename the columns
  dfa = df[cols]
  dfa.columns = col_names

  return dfa

def filter_psms(df_original, df, config):
  logger.info("Filtering PSMs...")

  # load the filtering functions specified by the input config
  filters = config["filters"]

  # each filter has a specified required column from the dataframe
  # make sure these columns exist before proceeding
  for i, f in enumerate(filters):
    # for each required column in the filter, check if it exists
    for j in required_cols[f["name"]]:
      if j not in df.columns:
        raise ValueError("Filter {} required a column {}, but this was not found in the input dataframe.".format(f["name"], j))

  # by default, exclude nothing. we'll use binary ORs (|) to
  # gradually add more and more observations to this exclude blacklist
  df["exclude"] = np.repeat(False, df.shape[0])

  # run all the filters specified by the list in the input config file
  # all filter functions are passed df_original, df, and the run configuration
  # after each filter, append it onto the exclusion master list with a bitwise OR
  # if the filter function returns None, then just ignore it.
  for i, f in enumerate(filters):
    e = filter_funcs[f["name"]](df_original, df, config, f)
    if e is not None:
      df["exclude"] = (df["exclude"] | e)

  return df, df_original

def process_files(config):

  # create our output data frames
  df_original = pd.DataFrame()
  df = pd.DataFrame()

  # iterate through each input file provided.
  for i, f in enumerate(config["input"]):
    # first expand user or any vars
    f = os.path.expanduser(f)
    f = os.path.expandvars(f)

    logger.info("Reading in input file #{} | {} ...".format(i, f))

    # load the input file with pandas
    # 
    # have a variable low memory option depending on the input type.
    # MaxQuant, for example, has a structure that forces pandas out of its
    # optimal low memory mode, and we have to specify it here.
    dfa = pd.read_csv(f, sep="\t", low_memory=config["low_memory"])

    # keep track of where observations came from. this is _not_ the raw file ID
    # but instead the ID from which input file it originated from, so that if
    # we need to split these observations up by input file in the future we can do so
    dfa["input_id"] = i

    # append a copy of dfa into df_original, because the conversion process will heavily
    # modify dfa. we need to keep a copy of the original dataframe in order to append
    # the new columns back onto it later.
    df_original = df_original.append(dfa)

    logger.info("Converting {} ({} PSMs)...".format(f, dfa.shape[0]))

    # convert - takes subset of columns and renames them
    dfa = convert(dfa, config)

    # need to reset the input_id after the conversion process
    dfa["input_id"] = i
    # append to master dataframe
    df = df.append(dfa)

  # create a unique ID for each PSM to help with stiching the final result together
  # after all of our operations
  df["id"] = range(0, df.shape[0])
  df_original["id"] = range(0, df.shape[0])

  # remove experiments from blacklist
  # by default, exclude nothing from the original experiment
  df_original["input_exclude"] = np.repeat(False, df_original.shape[0])
  if "exclude_exps" in config and config["exclude_exps"] is not None:
    if len(config["exclude_exps"]) <= 0:
      logger.warning("Experiment exclusion by raw file name provided, but expression is defined incorrectly. Skipping this filter.")
    else:
      # see if any raw file names match the user-provided expression
      exclude_exps = list(filter(lambda x: re.search(r"" + config["exclude_exps"] + "", x), df["raw_file"].unique()))

      logger.info("Filtering out {} observations matching \"{}\"".format(np.sum(df["raw_file"].isin(exclude_exps)), config["exclude_exps"]))

      # remove excluded rows from the sparse dataframe,
      # but keep them in the original data frame, so that we can stitch together
      # the final output later
      exclude_exps = df["raw_file"].isin(exclude_exps).values
      df = df[~exclude_exps]

      # keep track of which experiments were excluded in 
      df_original["input_exclude"] = exclude_exps
  else:
    logger.info("No experiment exclusion list provided. Skipping this filter.")

  logger.info("{} PSMs loaded from input file(s)".format(df.shape[0]))

  # just a quick index reset, in case any observations were completely removed
  # in the experiment blacklist step
  df = df.reset_index(drop=True)

  # map peptide and experiment IDs
  # sort experiment IDs alphabetically - or else the order is by 
  # first occurrence of an observation of that raw file
  df["exp_id"] = df["raw_file"].map({ind: val for val, ind in enumerate(np.sort(df["raw_file"].unique()))})
  df["peptide_id"] = df["sequence"].map({ind: val for val, ind in enumerate(df["sequence"].unique())})

  # run filters for all PSMs
  # filtered-out PSMs are not removed from the dataframe, but are instead flagged
  # using the "exclude" column
  # when the alignment is run later, then these PSMs will be removed
  df, df_original = filter_psms(df_original, df, config)

  # only take the four required columns (+ the IDs) with us
  # the rest were only needed for filtering and can be removed
  df = df[["sequence", "raw_file", "retention_time", "pep", "exp_id", "peptide_id", "input_id", "id", "exclude"]]

  # sort by peptide_id, exp_id
  df = df.sort_values(["peptide_id", "exp_id"])

  return df, df_original

def main():
  # load command-line args
  parser = argparse.ArgumentParser()  
  add_global_args(parser)
  args = parser.parse_args()

  # load config file
  # this function also creates the output folder
  config = read_config_file(args)

  # initialize logger
  init_logger(config["verbose"], os.path.join(config["output"], "converter.log"))

  # process all input files (converts and filters)
  df, df_original = process_files(config)
  
  logger.info("{} / {} ({:.2%}) observations pass criteria and will be used for alignment".format(df.shape[0] - df["exclude"].sum(), df.shape[0], (df.shape[0] - df["exclude"].sum()) / df.shape[0]))

  # write to file
  if config["combine_output"]:
    # if combining input files, then write to one combined file
    out_path = os.path.join(config["output"], config["combined_output_name"])
    logger.info("Combining input file(s) and writing adjusted data file to {} ...".format(out_path))
    df.to_csv(out_path, sep="\t", index=False)
  else:
    # if keeping input files separate, then use "input_id" to retain the
    # order in which the input files were passed in
    logger.info("Saving output to separate files...")
    for i, f in enumerate(config["input"]):
      out_path = os.path.join(config["output"], os.path.splitext(os.path.basename(f))[0] + config["output_suffix"] + "_" + str(i) + ".txt")
      logger.info("Saving input file {} to {}".format(i, out_path))
      df_a = df.loc[df["input_id"] == i]
      df_a.to_csv(out_path, sep="\t", index=False)

if __name__ == "__main__":
  main()
