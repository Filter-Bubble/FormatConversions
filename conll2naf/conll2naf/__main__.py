import conll2naf
import conllu
import os
import argparse
import sys

DEFAULT_FEATURES = ['id', 'form', 'lemma', 'upos', 'xpos', 'feats', 'head',
                    'deprel', 'deps', 'misc', 'frame', 'role']




parser = argparse.ArgumentParser(description='Conversion script from conll to NAF')
parser.add_argument('input_file', type=str)
parser.add_argument('-o', '--out_dir', dest='out_dir', default='.', type=str, help='output directory')
parser.add_argument('--file_per_sent', dest='file_per_sent', default=False,
                    const=True, action='store_const',
                    help='Output one file per sentence')

args = parser.parse_args()

conll2naf.build_naf(args.input_file, DEFAULT_FEATURES, args.out_dir, args.file_per_sent)
