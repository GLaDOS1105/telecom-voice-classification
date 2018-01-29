""" Author: Sean Wu
    NCU CSIE 3B, Taiwan

The indentification for single target audio file. Basically, this file add some pre-processing
and post-processing for the pattern comparison. Following is the explanation.

Pre-Processing
--------------
1. Read and get golden patterns
2. Convert the target waveform file into specific format (also create as .tmp file)
3. Get the MFCC pattern of target file

then feed the MFCC pattern of target file into `pattern_cmp`.

Post-Processing
---------------
1. Delete .tmp file created by pre-processing step 2.
2. Return the result of comparison

"""

import time
import os
from os.path import join, isfile, basename
import pickle
import sys
import subprocess
import scipy.io.wavfile as wav
from python_speech_features import mfcc
from ptns_cmp import ptns_cmp

class Result():
    """ An object containing both raw and analyzed result calculated from patterns comparison. """
    def __init__(self, filepath, diff_indice, exe_time):
        self.diff_indice = diff_indice
        self.filepath = filepath
        self.exe_time = exe_time

    @property
    def filename(self):
        """ Get the filename of the target pattern. """
        return basename(self.filepath)

    @property
    def matched_golden_ptn(self):
        """ Get which golden pattern is the matched one. """
        return (min(self.diff_indice, key=self.diff_indice.get), min(self.diff_indice.values()))

    @property
    def mrd(self):
        """ Get the maximum difference among difference indice. """
        return max(self.diff_indice.values()) - min(self.diff_indice.values())

    @property
    def result_type(self):
        """ Check the result is typical, successful or not, which returns the full uppercase string.
        The default typical detect conditions is set by trail and error in following settings:
            (threshold=1500, scan_step=3) or (threshold=None, scan_step=1)
        TODO: This shold be optimized by machine learning classifier.
        """
        if self.mrd < 2000 and self.matched_golden_ptn[1] > 2000:
            return 'TYPICAL'
        return str(self.filename[:2] == self.matched_golden_ptn[0][:2]).upper()

def televoice_identify(filepath, threshold=None, scan_step=1, multiproc=False):
    """ Calculate the difference indices between target audio and each golden audio wavfiles.

    Parameters
    ----------
    filepath : string
        The path of target file (to be compared).
    threshold : float
        The threshold for the least difference to break the comparison.
    scan_step : integer
        The step of scanning on frame of target MFCC pattern.
    multiproc : boolean
        If `True`, the comparing process will run in multicore of CPU, and vice versa.

    Return
    ------
    A Result object containing the difference indices between target audio and each golden audio
      wavfiles as well as other comparison analysis.
    """
    start_time = time.time()

    # load golden wavfiles
    golden_ptns = read_golden_ptns(join("golden_wav"))

    # set the filepath for the output wavfile converted by ffmpeg
    tmp_filepath = join("temp", basename(filepath) + ".tmp")

    # Call the ffmpeg to convert (normalize) the input audio into:
    #    sample rate    8000 Hz
    #    bit depth      16
    #    channels       mono (left channel only, since the target channel is the left one)
    try:
        subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'panic', '-i', filepath,
                        '-af', 'pan=mono|c0=c0', '-ar', '8000', '-sample_fmt', 's16', '-f', 'wav',
                        tmp_filepath])
    except FileNotFoundError:
        print("[Error] Require ffmpeg to convert the audio in sepcific format.")
        sys.exit(2)    # ffmpeg require

    # read the target wavfile
    (rate, sig) = wav.read(tmp_filepath)

    # get the MFCC feature of target wavfile
    target_mfcc = mfcc(sig, rate, appendEnergy=False)

    # get the comparison result of target wavfile
    result = Result(filepath,
                    ptns_cmp(golden_ptns, target_mfcc, threshold, scan_step, multiproc),
                    time.time() - start_time)

    # detele the tmp file generated by ffmpeg
    try:
        os.remove(tmp_filepath) # remove the tmp file
    except OSError:
        pass

    return result

def read_golden_ptns(folderpath):
    """ Read every id pattern in folderpath. If there exists a pickle, use it.

    Parameters
    ----------
    folderpath : string
        The folderpath for the golden-pattern wavfiles.

    Return
    ------
    The dictionary of golden patterns.
    """
    while True: # keep trying to open the pickle file if an error occurs
        try:
            with open(join("temp", "golden_ptns.pickle"), 'rb') as pfile:
                return pickle.load(pfile)
        except FileNotFoundError: # the pickle file does not exist
            # get every paths of file in folderpath
            paths = (join(folderpath, f) for f
                     in os.listdir(folderpath) if isfile(join(folderpath, f)))
            # get MFCC feature
            golden_ptns = dict()
            for path in paths:
                (rate, sig) = wav.read(path)
                golden_ptns[basename(path)] = mfcc(sig, rate, appendEnergy=False)
            with open(join("temp", "golden_ptns.pickle"), 'wb') as pfile: # save the pickle binary
                pickle.dump(golden_ptns, pfile, protocol=pickle.HIGHEST_PROTOCOL)
            return golden_ptns
        except EOFError: # the pickle file created but binary content haven't been written in
            print("[Warning] Try to load golden_ptns.pickle but is empty, automatically retrying..")
            continue # retry opening pickle file
        except pickle.UnpicklingError as err:
            print("[Warning] Try to load golden_ptns.pickle but {}"
                  "Automatically retrying..".format(err))
            continue
