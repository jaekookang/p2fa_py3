#!/usr/bin/env python

import unittest
import os
import subprocess
import tempfile
import filecmp
from p2fa import align

module_path = os.path.dirname(align.__file__)


class P2FATest(unittest.TestCase):
    input_wav = os.path.join(module_path, 'examples', 'ploppy.wav')
    input_transcription = os.path.join(module_path, 'examples', 'ploppy.txt')
    outfile = os.path.join(tempfile.gettempdir(), 'ploppy.gen.TextGrid')
    true_alignment_file = os.path.join(module_path, 'examples', 'ploppy.TextGrid')

    def test_aligner(self):
        align.align(self.input_wav, self.input_transcription, self.outfile)
        self.assertTrue(filecmp.cmp(self.outfile, self.true_alignment_file))

    def test_standalone_aligner(self):
        subprocess.run(['p2fa/align.py', self.input_wav, self.input_transcription, self.outfile])
        self.assertTrue(filecmp.cmp(self.outfile, self.true_alignment_file))
