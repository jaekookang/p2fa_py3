#!/usr/bin/env python

""" Command-line usage:
      python align.py [options] wave_file transcript_file output_file
      where options may include:
      	-r sampling_rate -- override which sample rate model to use, one of 8000, 11025, and 16000
        -s start_time    -- start of portion of wavfile to align (in seconds, default 0)
        -e end_time      -- end of portion of wavfile to align (in seconds, defaul to end)
			
	You can also import this file as a module and use the functions directly.

	2018-02-22 JK, This file was modified for Python3.x 
"""

import os
import sys
import getopt
import wave
import re


def prep_wav(orig_wav, out_wav, sr_override, wave_start, wave_end):
    global sr_models

    if os.path.exists(out_wav) and False:
        f = wave.open(out_wav, 'r')
        SR = f.getframerate()
        f.close()
        print("Already re-sampled the wav file to " + str(SR))
        return SR

    f = wave.open(orig_wav, 'r')
    SR = f.getframerate()
    f.close()

    soxopts = ""
    if float(wave_start) != 0.0 or wave_end != None:
        soxopts += " trim " + wave_start
        if wave_end != None:
            soxopts += " " + str(float(wave_end) - float(wave_start))

    if (sr_models != None and SR not in sr_models) or (sr_override != None and SR != sr_override) or soxopts != "":
        new_sr = 11025
        if sr_override != None:
            new_sr = sr_override

        print("Resampling wav file from " + str(SR) +
              " to " + str(new_sr) + soxopts + "...")
        SR = new_sr
        os.system("sox " + orig_wav + " -r " + str(SR) +
                  " " + out_wav + " polyphase" + soxopts)
    else:
        # print("Using wav file, already at sampling rate " + str(SR) + ".")
        os.system("cp -f " + orig_wav + " " + out_wav)

    return SR


def prep_mlf(trsfile, mlffile, word_dictionary, surround, between):
        # Read in the dictionary to ensure all of the words
        # we put in the MLF file are in the dictionary. Words
        # that are not are skipped with a warning.
    f = open(word_dictionary, 'r')
    dict = {}  # build hash table
    for line in f.readlines():
        if line != "\n" and line != "":
            dict[line.split()[0]] = True
    f.close()

    f = open(trsfile, 'r')
    lines = f.readlines()
    f.close()

    words = []

    if surround != None:
        words += surround.split(',')

    i = 0

    # this pattern matches hyphenated words, such as TWENTY-TWO; however, it doesn't work with longer things like SOMETHING-OR-OTHER
    hyphenPat = re.compile(r'([A-Z]+)-([A-Z]+)')

    while (i < len(lines)):
        txt = lines[i].replace('\n', '')
        txt = txt.replace('{breath}', '{BR}').replace('&lt;noise&gt;', '{NS}')
        txt = txt.replace('{laugh}', '{LG}').replace('{laughter}', '{LG}')
        txt = txt.replace('{cough}', '{CG}').replace('{lipsmack}', '{LS}')

        for pun in [',', '.', ':', ';', '!', '?', '"', '%', '(', ')', '--', '---']:
            txt = txt.replace(pun,  '')

        txt = txt.upper()

        # break up any hyphenated words into two separate words
        txt = re.sub(hyphenPat, r'\1 \2', txt)

        txt = txt.split()

        for wrd in txt:
            if (wrd in dict):
                words.append(wrd)
                if between != None:
                    words.append(between)
            else:
                print("SKIPPING WORD", wrd)

        i += 1

    # remove the last 'between' token from the end
    if between != None:
        words.pop()

    if surround != None:
        words += surround.split(',')

    writeInputMLF(mlffile, words)


def writeInputMLF(mlffile, words):
    fw = open(mlffile, 'w')
    fw.write('#!MLF!#\n')
    fw.write('"*/tmp.lab"\n')
    for wrd in words:
        fw.write(wrd + '\n')
    fw.write('.\n')
    fw.close()


def readAlignedMLF(mlffile, SR, wave_start):
        # This reads a MLFalignment output  file with phone and word
        # alignments and returns a list of words, each word is a list containing
        # the word label followed by the phones, each phone is a tuple
        # (phone, start_time, end_time) with times in seconds.

    f = open(mlffile, 'r')
    lines = [l.rstrip() for l in f.readlines()]
    f.close()

    if len(lines) < 3:
        raise ValueError("Alignment did not complete succesfully.")

    j = 2
    ret = []
    while (lines[j] != '.'):
        # Is this the start of a word; do we have a word label?
        if (len(lines[j].split()) == 5):
            # Make a new word list in ret and put the word label at the beginning
            wrd = lines[j].split()[4]
            ret.append([wrd])

        # Append this phone to the latest word (sub-)list
        ph = lines[j].split()[2]
        if (SR == 11025):
            st = (float(lines[j].split()[0]) /
                  10000000.0 + 0.0125) * (11000.0 / 11025.0)
            en = (float(lines[j].split()[1]) /
                  10000000.0 + 0.0125) * (11000.0 / 11025.0)
        else:
            st = float(lines[j].split()[0]) / 10000000.0 + 0.0125
            en = float(lines[j].split()[1]) / 10000000.0 + 0.0125
        if st < en:
            ret[-1].append([ph, st + wave_start, en + wave_start])

        j += 1

    return ret


def writeTextGrid(outfile, word_alignments):
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

    # write the phone interval tier
    fw = open(outfile, 'w')
    fw.write('File type = "ooTextFile short"\n')
    fw.write('"TextGrid"\n')
    fw.write('\n')
    fw.write(str(phons[0][1]) + '\n')
    fw.write(str(phons[-1][2]) + '\n')
    fw.write('<exists>\n')
    fw.write('2\n')
    fw.write('"IntervalTier"\n')
    fw.write('"phone"\n')
    fw.write(str(phons[0][1]) + '\n')
    fw.write(str(phons[-1][-1]) + '\n')
    fw.write(str(len(phons)) + '\n')
    for k in range(len(phons)):
        fw.write(str(phons[k][1]) + '\n')
        fw.write(str(phons[k][2]) + '\n')
        fw.write('"' + phons[k][0] + '"' + '\n')

    # write the word interval tier
    fw.write('"IntervalTier"\n')
    fw.write('"word"\n')
    fw.write(str(phons[0][1]) + '\n')
    fw.write(str(phons[-1][-1]) + '\n')
    fw.write(str(len(wrds)) + '\n')
    for k in range(len(wrds) - 1):
        fw.write(str(wrds[k][1]) + '\n')
        fw.write(str(wrds[k + 1][1]) + '\n')
        fw.write('"' + wrds[k][0] + '"' + '\n')

    fw.write(str(wrds[-1][1]) + '\n')
    fw.write(str(phons[-1][2]) + '\n')
    fw.write('"' + wrds[-1][0] + '"' + '\n')

    fw.close()


def prep_working_directory():
    os.system("rm -r -f ./tmp")
    os.system("mkdir ./tmp")


def delete_working_directory():
    os.system('rm -r -f ./tmp')


def prep_scp(wavfile):
    fw = open('./tmp/codetr.scp', 'w')
    fw.write(wavfile + ' ./tmp/tmp.plp\n')
    fw.close()
    fw = open('./tmp/test.scp', 'w')
    fw.write('./tmp/tmp.plp\n')
    fw.close()


def create_plp(hcopy_config):
    os.system('HCopy -T 1 -C ' + hcopy_config + ' -S ./tmp/codetr.scp')


def viterbi(input_mlf, word_dictionary, output_mlf, phoneset, hmmdir):
    os.system('HVite -T 1 -a -m -I ' + input_mlf + ' -H ' + hmmdir + '/macros -H ' + hmmdir + '/hmmdefs  -S ./tmp/test.scp -i ' +
              output_mlf + ' -p 0.0 -s 5.0 ' + word_dictionary + ' ' + phoneset + ' > ./tmp/aligned.results')


def getopt2(name, opts, default=None):
    value = [v for n, v in opts if n == name]
    if len(value) == 0:
        return default
    return value[0]


if __name__ == '__main__':

    try:
        opts, args = getopt.getopt(sys.argv[1:], "r:s:e:", ["model="])

        # get the three mandatory arguments
        if len(args) != 3:
            raise ValueError(
                "Specify wavefile, a transcript file, and an output file!")

        wavfile, trsfile, outfile = args

        sr_override = getopt2("-r", opts, None)
        wave_start = getopt2("-s", opts, "0.0")
        wave_end = getopt2("-e", opts, None)
        surround_token = "sp"  # getopt2("-p", opts, 'sp')
        between_token = "sp"  # getopt2("-b", opts, 'sp')

        if surround_token.strip() == "":
            surround_token = None
        if between_token.strip() == "":
            between_token = None

        mypath = getopt2("--model", opts, None)
    except:
        print(__doc__)
        (type, value, traceback) = sys.exc_info()
        print(value)
        sys.exit(0)

    # If no model directory was said explicitly, get directory containing this script.
    hmmsubdir = ""
    sr_models = None
    if mypath == None:
        mypath = os.path.dirname(os.path.abspath(sys.argv[0])) + "/model"
        hmmsubdir = "FROM-SR"
        # sample rates for which there are acoustic models set up, otherwise
        # the signal must be resampled to one of these rates.
        sr_models = [8000, 11025, 16000]

    if sr_override != None and sr_models != None and not sr_override in sr_models:
        raise Exception("invalid sample rate: not an acoustic model available")

    word_dictionary = "./tmp/dict"
    input_mlf = './tmp/tmp.mlf'
    output_mlf = './tmp/aligned.mlf'

    # create working directory
    prep_working_directory()

    # create ./tmp/dict by concatening our dict with a local one
    if os.path.exists("dict.local"):
        os.system("cat " + mypath + "/dict dict.local > " + word_dictionary)
    else:
        os.system("cat " + mypath + "/dict > " + word_dictionary)

    # prepare wavefile: do a resampling if necessary
    tmpwav = "./tmp/sound.wav"
    SR = prep_wav(wavfile, tmpwav, sr_override, wave_start, wave_end)

    if hmmsubdir == "FROM-SR":
        hmmsubdir = "/" + str(SR)

    # prepare mlfile
    prep_mlf(trsfile, input_mlf, word_dictionary,
             surround_token, between_token)

    # prepare scp files
    prep_scp(tmpwav)

    # generate the plp file using a given configuration file for HCopy
    create_plp(mypath + hmmsubdir + '/config')

    # run Verterbi decoding
    #print("Running HVite...")
    mpfile = mypath + '/monophones'
    if not os.path.exists(mpfile):
        mpfile = mypath + '/hmmnames'
    viterbi(input_mlf, word_dictionary, output_mlf, mpfile, mypath + hmmsubdir)

    # output the alignment as a Praat TextGrid
    writeTextGrid(outfile, readAlignedMLF(output_mlf, SR, float(wave_start)))

    # clean directory
    delete_working_directory()
    
