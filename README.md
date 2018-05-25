# P2FA for Python3.x

This is a modified version of P2FA for Python3 compatibility. Everything else remains the same as the original P2FA. Forced alignment helps to align linguistic units (e.g., phoneme or words) with the corresponding sound file. All you need is to have a sound file with a transcription file. The output will be .TextGrid file with time-aligned phone and word tiers.

This was tested on macOS Sierra. It should work fine on Linux too.

## Install HTK
First, you need to download HTK source code (http://htk.eng.cam.ac.uk/).
This HTK installation guide is retrieved from [Link](https://github.com/prosodylab/Prosodylab-Aligner). Installation is based on macOS Sierra.

Unzip HTK-3.4.1.tar.gz file

```bash
$ tar -xvf HTK-3.4.1.tar.gz
```

After extracting the tar file, switch to htk directory.

```bash
$ cd htk
```

Compile HTK in the htk directory.

```bash
$ export CPPFLAGS=-UPHNALG
$ ./configure --disable-hlmtools --disable-hslab
$ make clean    # necessary if you're not starting from scratch
$ make -j4 all
$ sudo make -j4 install
```

## Install sox

```bash
$ sudo apt-get install sox

# or using brew

$ brew install sox
```

## Run

```bash
$ python align.py examples/ploppy.wav examples/ploppy.txt examples/ploppy.TextGrid
```

## Result

![image_of_ploppy_dot_png](_tmp/ploppy.png)

## Source
- http://www.ling.upenn.edu/phonetics/p2fa/
- Jiahong Yuan and Mark Liberman. 2008. Speaker identification on the SCOTUS corpus. Proceedings of Acoustics '08.
- https://github.com/prosodylab/Prosodylab-Aligner (P2FA seems better than Prosodylab-Aligner based on my qualitative evaluation)
- State-level aligner: [Link](https://github.com/jaekookang/p2fa_state_aligner)
