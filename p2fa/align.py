#!/usr/bin/env python

""" Command-line usage:
      python align.py [options] wave_file transcript_file output_file
      where options may include:
        -r sampling_rate -- override which sample rate model to use, one of 8000, 11025, and 16000
        -s start_time    -- start of portion of wavfile to align (in seconds, default 0)
        -e end_time      -- end of portion of wavfile to align (in seconds, default to end)
        -t state_align   -- align HMM states (eg. s1, s2, s3) additionally; default=0
        -v verbose       -- print HCopy and HVite commandline; default=0

    You can also import this file as a module and use the functions directly.

    2018-02-22 JK, This file was modified for Python3.x
    2018-08-21  papagandalf, This file was modified so that it can be called from Python code
    2020-06-20 JK, command-line option fixed; 
                   verbose option added for debugging;
                   state-level alignment added;
"""

import os
import wave
import re
import shutil
import tempfile
import argparse


TEMP_DIR = os.path.join(tempfile.gettempdir(), 'p2fa')
LOG_LIKELIHOOD_REGEX = r'.+==\s+\[\d+ frames\]\s+(-?\d+.\d+)'


def prep_wav(orig_wav, out_wav, sr_override, wave_start, wave_end, sr_models):
    if os.path.exists(out_wav) and False:
        f = wave.open(out_wav, 'r')
        sr = f.getframerate()
        f.close()
        print("Already re-sampled the wav file to " + str(sr))
        return sr

    f = wave.open(orig_wav, 'r')
    SR = f.getframerate()
    f.close()

    soxopts = ""
    if float(wave_start) != 0.0 or wave_end is not None:
        soxopts += " trim " + wave_start
        if wave_end is not None:
            soxopts += " " + str(float(wave_end) - float(wave_start))

    if (sr_models is not None and SR not in sr_models) or (
            sr_override is not None and SR != sr_override) or soxopts != "":
        new_sr = 11025
        if sr_override is not None:
            new_sr = sr_override

        print("Resampling wav file from " + str(SR) +
              " to " + str(new_sr) + soxopts + "...")
        SR = new_sr
        os.system("sox " + orig_wav + " -r " + str(SR) +
                  " " + out_wav + " " + soxopts)
    else:
        # print("Using wav file, already at sampling rate " + str(SR) + ".")
        os.system("cp -f " + orig_wav + " " + out_wav)

    return SR


def prep_mlf(trsfile, mlffile, word_dictionary, surround, between):
    # Read in the dictionary to ensure all of the words
    # we put in the MLF file are in the dictionary. Words
    # that are not are skipped with a warning.
    f = open(word_dictionary, 'r')
    the_dict = {}  # build hash table
    for line in f.readlines():
        if line != "\n" and line != "":
            the_dict[line.split()[0]] = True
    f.close()

    f = open(trsfile, 'r')
    lines = f.readlines()
    f.close()

    words = []

    if surround is not None:
        words += surround.split(',')

    i = 0

    # this pattern matches hyphenated words, such as TWENTY-TWO;
    # however, it doesn't work with longer things like SOMETHING-OR-OTHER
    hyphen_pat = re.compile(r'([A-Z]+)-([A-Z]+)')

    while i < len(lines):
        txt = lines[i].replace('\n', '')
        txt = txt.replace('{breath}', '{BR}').replace('&lt;noise&gt;', '{NS}')
        txt = txt.replace('{laugh}', '{LG}').replace('{laughter}', '{LG}')
        txt = txt.replace('{cough}', '{CG}').replace('{lipsmack}', '{LS}')

        for pun in [',', '.', ':', ';', '!', '?', '"', '%', '(', ')', '--', '---']:
            txt = txt.replace(pun, '')

        txt = txt.upper()

        # break up any hyphenated words into two separate words
        txt = re.sub(hyphen_pat, r'\1 \2', txt)

        txt = txt.split()

        for wrd in txt:
            if wrd in the_dict:
                words.append(wrd)
                if between is not None:
                    words.append(between)
            else:
                print("SKIPPING WORD", wrd)

        i += 1

    # remove the last 'between' token from the end
    if between is not None:
        words.pop()

    if surround is not None:
        words += surround.split(',')

    write_input_mlf(mlffile, words)


def write_input_mlf(mlffile, words):
    fw = open(mlffile, 'w')
    fw.write('#!MLF!#\n')
    fw.write('"*/tmp.lab"\n')
    for wrd in words:
        fw.write(wrd + '\n')
    fw.write('.\n')
    fw.close()


# def read_aligned_mlf(mlffile, sr, wave_start):
#     # This reads a MLFalignment output  file with phone and word
#     # alignments and returns a list of words, each word is a list containing
#     # the word label followed by the phones, each phone is a tuple
#     # (phone, start_time, end_time) with times in seconds.

#     f = open(mlffile, 'r')
#     lines = [l.rstrip() for l in f.readlines()]
#     f.close()

#     if len(lines) < 3:
#         raise ValueError("Alignment did not complete succesfully.")

#     j = 2
#     ret = []
#     while lines[j] != '.':
#         # Is this the start of a word; do we have a word label?
#         if len(lines[j].split()) == 5:
#             # Make a new word list in ret and put the word label at the beginning
#             wrd = lines[j].split()[4]
#             ret.append([wrd])

#         # Append this phone to the latest word (sub-)list
#         ph = lines[j].split()[2]
#         if sr == 11025:
#             st = (float(lines[j].split()[0]) /
#                   10000000.0 + 0.0125) * (11000.0 / 11025.0)
#             en = (float(lines[j].split()[1]) /
#                   10000000.0 + 0.0125) * (11000.0 / 11025.0)
#         else:
#             st = float(lines[j].split()[0]) / 10000000.0 + 0.0125
#             en = float(lines[j].split()[1]) / 10000000.0 + 0.0125
#         if st < en:
#             ret[-1].append([ph, st + wave_start, en + wave_start])

#         j += 1

#     return ret

def read_aligned_mlf(mlffile, SR, wave_start):
    # This reads a MLFalignment output  file with phone and word
    # alignments and returns a list of words, each word is a list containing
    # the word label followed by the phones, each phone is a tuple
    # (phone, start_time, end_time) with times in seconds.
    #
    # TODO: extract log-likelihood score
    
    f = open(mlffile, 'r')
    lines = [l.rstrip() for l in f.readlines()]
    f.close()

    if len(lines) < 3 :
        raise ValueError("Alignment did not complete succesfully.")
        
    j = 2
    phon = []
    ret = []
    while (lines[j] != '.'):
        if (len(lines[j].split()) >= 5): # Is this the start of a word; do we have a word label?
            # Make a new word list in ret and put the word label at the beginning
            wrd = lines[j].split()[4]
            ret.append([wrd])
    
        # Append this phone to the latest word (sub-)list
        ph = lines[j].split()[2]
        if (SR == 11025):
            st = (float(lines[j].split()[0])/10000000.0 + 0.0125)*(11000.0/11025.0)
            en = (float(lines[j].split()[1])/10000000.0 + 0.0125)*(11000.0/11025.0)
        else:
            st = float(lines[j].split()[0])/10000000.0 + 0.0125
            en = float(lines[j].split()[1])/10000000.0 + 0.0125   
        if st < en:
            ret[-1].append([ph, st+wave_start, en+wave_start])
 
        j += 1
    
    return ret


def make_alignment_lists(word_alignments):
    # make the list of just phone alignments
    phons = []
    for wrd in word_alignments:
        phons.extend(wrd[1:])  # skip the word label

    # make the list of just word alignments
    # we're getting elements of the form:
    #   ["word label", ["phone1", start, end], ["phone2", start, end], ...]
    wrds = []
    for wrd in word_alignments:
        # If no phones make up this word, then it was an optional word
        # like a pause that wasn't actually realized.
        if len(wrd) == 1:
            continue
        # word label, first phone start time, last phone end time
        wrds.append([wrd[0], wrd[1][1], wrd[-1][2]])
    return phons, wrds


def get_av_log_likelihood_per_frame(file_path):
    with open(file_path, 'r') as f:
        lines = f.read().splitlines()

    score = re.match(LOG_LIKELIHOOD_REGEX, lines[-1]).groups()[0]

    return float(score)


def write_text_grid(outfile, word_alignments, state_alignments=None) :
    # make the list of just phone alignments
    phons = []
    for wrd in word_alignments :
        phons.extend(wrd[1:]) # skip the word label

    # make the list of just state alignments
    if state_alignments is not None:
        states = []
        for sts in state_alignments:
            states.extend(sts[1:]) # skip the phone label
    
    # make the list of just word alignments
    # we're getting elements of the form:
    #   ["word label", ["phone1", start, end], ["phone2", start, end], ...]
    wrds = []
    for wrd in word_alignments :
        # If no phones make up this word, then it was an optional word
        # like a pause that wasn't actually realized.
        if len(wrd) == 1 :
            continue
        wrds.append([wrd[0], wrd[1][1], wrd[-1][2]]) # word label, first phone start time, last phone end time
    
    fw = open(outfile, 'w')
    fw.write('File type = "ooTextFile short"\n')
    fw.write('"TextGrid"\n')
    fw.write('\n')
    fw.write(str(phons[0][1]) + '\n')
    fw.write(str(phons[-1][-1]) + '\n')
    fw.write('<exists>\n')
    if state_alignments is not None:
        fw.write('3\n')
    else:
        fw.write('2\n')

    #write the state interval tier
    if state_alignments is not None:
        fw.write('"IntervalTier"\n')
        fw.write('"state"\n')
        fw.write(str(states[0][1]) + '\n')
        fw.write(str(states[-1][-1]) + '\n')
        fw.write(str(len(states)) + '\n')
        for k in range(len(states)):
            fw.write(str(states[k][1]) + '\n')
            fw.write(str(states[k][2]) + '\n')
            fw.write('"' + states[k][0] + '"' + '\n')
        
    #write the phone interval tier
    fw.write('"IntervalTier"\n')
    fw.write('"phone"\n')
    fw.write(str(phons[0][1]) + '\n')
    fw.write(str(phons[-1][-1]) + '\n')
    fw.write(str(len(phons)) + '\n')
    for k in range(len(phons)):
        fw.write(str(phons[k][1]) + '\n')
        fw.write(str(phons[k][2]) + '\n')
        fw.write('"' + phons[k][0] + '"' + '\n')

    #write the word interval tier
    fw.write('"IntervalTier"\n')
    fw.write('"word"\n')
    fw.write(str(phons[0][1]) + '\n')
    fw.write(str(phons[-1][-1]) + '\n')
    fw.write(str(len(wrds)) + '\n')
    for k in range(len(wrds) - 1):
        fw.write(str(wrds[k][1]) + '\n')
        fw.write(str(wrds[k+1][1]) + '\n')
        fw.write('"' + wrds[k][0] + '"' + '\n')
    fw.write(str(wrds[-1][1]) + '\n')
    fw.write(str(phons[-1][2]) + '\n')
    fw.write('"' + wrds[-1][0] + '"' + '\n')  
    
    fw.close()    


def prep_working_directory():
    delete_working_directory()
    os.mkdir(TEMP_DIR)


def delete_working_directory():
    try:
        shutil.rmtree(TEMP_DIR)
    except OSError:
        pass


def prep_scp(wavfile):
    fw = open(os.path.join(TEMP_DIR, 'codetr.scp'), 'w')
    fw.write(wavfile + ' ' + os.path.join(TEMP_DIR, 'tmp.plp') + '\n')
    fw.close()
    fw = open(os.path.join(TEMP_DIR, 'test.scp'), 'w')
    fw.write(os.path.join(TEMP_DIR, 'tmp.plp') + '\n')
    fw.close()


def create_plp(hcopy_config, verbose=False):
    #os.system('HCopy -T 1 -C ' + hcopy_config + ' -S ' + os.path.join(TEMP_DIR, 'codetr.scp'))
    cmd = (
        'HCopy -T 1'
        f' -C {hcopy_config}'
        f' -S {os.path.join(TEMP_DIR, "codetr.scp")}'
        )
    if verbose:
        print('creating plp...\n', cmd)

    os.system(cmd)


def viterbi(input_mlf, word_dictionary, output_mlf, phoneset, hmmdir, state_align=False, verbose=False):
    if state_align:
        salign = ' -f -y lab'
    else:
        salign = ''

    cmd = (
        'HVite -T 1 -a -m'
        f'{salign}'
        f' -I {input_mlf}'
        f' -H {os.path.join(hmmdir, "macros")}'
        f' -H {os.path.join(hmmdir, "hmmdefs")}'
        f' -S {os.path.join(TEMP_DIR, "test.scp")}'
        f' -i {output_mlf}'
        f' -p 0.0 -s 5.0'
        f' {word_dictionary}'
        f' {phoneset}'
        f' > {os.path.join(TEMP_DIR, "aligned.results")}'
        )
    
    if verbose:
        print('running viterbi...\n', cmd)
    os.system(cmd)


def align(wavfile, trsfile, outfile=None, wave_start='0.0', wave_end=None, sr_override=None, model_path=None, custom_dict=None, state_align=False, verbose=False):
    surround_token = "sp"
    between_token = "sp"

    # If no model directory was said explicitly, get directory containing this script.
    hmmsubdir = ""
    sr_models = None
    if model_path is None:
        model_path = os.path.dirname(os.path.realpath(__file__)) + "/model"
        hmmsubdir = "FROM-SR"
        # sample rates for which there are acoustic models set up, otherwise
        # the signal must be resampled to one of these rates.
        sr_models = [8000, 11025, 16000]

    if sr_override is not None and sr_models is not None and sr_override not in sr_models:
        raise Exception("invalid sample rate: not an acoustic model available")

    word_dictionary = os.path.join(TEMP_DIR, 'dict')
    input_mlf = os.path.join(TEMP_DIR, 'tmp.mlf')
    output_mlf = os.path.join(TEMP_DIR, 'aligned.mlf')
    results_mlf = os.path.join(TEMP_DIR, 'aligned.results')
    if state_align:
        state_mlf = os.path.join(TEMP_DIR, 'aligned_state.mlf')
    else:
        state_mlf = None

    # create working directory
    prep_working_directory()

    # create ./tmp/dict by concatening our dict with a local one
    if custom_dict is not None:
        os.system("cat " + model_path + "/dict " + custom_dict + " > " + word_dictionary)
    else:
        if os.path.exists("dict.local"):
            os.system("cat " + model_path + "/dict dict.local > " + word_dictionary)
        else:
            os.system("cat " + model_path + "/dict > " + word_dictionary)

    # prepare wavefile: do a resampling if necessary
    tmpwav = os.path.join(TEMP_DIR, 'sound.wav')
    sr = prep_wav(wavfile, tmpwav, sr_override, wave_start, wave_end, sr_models)

    if hmmsubdir == "FROM-SR":
        hmmsubdir = str(sr)

    # prepare mlfile
    prep_mlf(trsfile, input_mlf, word_dictionary,
             surround_token, between_token)

    # prepare scp files
    prep_scp(tmpwav)

    # generate the plp file using a given configuration file for HCopy
    create_plp(os.path.join(model_path, hmmsubdir, 'config'), verbose=verbose)

    # run Verterbi decoding
    # print("Running HVite...")
    mpfile = os.path.join(model_path, 'monophones')
    if not os.path.exists(mpfile):
        mpfile = os.path.join(model_path, 'hmmnames')
    
    viterbi(input_mlf, word_dictionary, output_mlf, mpfile, os.path.join(model_path, hmmsubdir), verbose=verbose)
    if state_align:
        viterbi(input_mlf, word_dictionary, state_mlf, mpfile, os.path.join(model_path, hmmsubdir), state_align=True, verbose=verbose)
        state_alignments = read_aligned_mlf(state_mlf, sr, float(wave_start))
    else:
        state_alignments = None

    _alignments = read_aligned_mlf(output_mlf, sr, float(wave_start))
    phoneme_alignments, word_alignments = make_alignment_lists(_alignments)

    av_score_per_frame = get_av_log_likelihood_per_frame(results_mlf)

    # output the alignment as a Praat TextGrid
    if outfile is not None:
        write_text_grid(outfile, _alignments, state_alignments=state_alignments)

    # clean directory
    delete_working_directory()
    if not state_align:
        return phoneme_alignments, word_alignments, av_score_per_frame
    else:
        return phoneme_alignments, word_alignments, state_alignments, av_score_per_frame


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P2FA for Python3 (https://github.com/jaekookang/p2fa_py3)')
    parser.add_argument('wavfile', type=str, help='Provide wav file with valid path')
    parser.add_argument('trsfile', type=str, help='Provide transcription file (txt) with valid path')
    parser.add_argument('outfile', type=str, help='Provide output filename (TextGrid) with valid path')
    parser.add_argument('-r', '--sampling_rate', type=int, default=11025, choices=[8000,11025,16000],
        help='override which sample rate model to use, one of 8000, 11025, and 16000')
    parser.add_argument('-s', '--start_time', default='0.0', 
        help='start of portion of wavfile to align (in seconds, default 0)')
    parser.add_argument('-e', '--end_time', default=None, 
        help='end of portion of wavfile to align (in seconds, defaul to end)')
    parser.add_argument('-t', '--state_align', type=int, default=0, choices=[0, 1], 
        help='align HMM states (eg. s1, s2, s3) additionally; default=0')
    parser.add_argument('-v', '--verbose', type=int, default='0', choices=[0, 1], 
        help='print HCopy and HVite commandlines; default=0')

    args = parser.parse_args()

    align(args.wavfile, args.trsfile, outfile=args.outfile, 
        wave_start=args.start_time, wave_end=args.end_time, 
        sr_override=args.sampling_rate, model_path=None, custom_dict=None, 
        state_align=int(args.state_align),
        verbose=int(args.verbose))
