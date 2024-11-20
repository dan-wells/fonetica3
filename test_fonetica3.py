#!/usr/bin/env python3

import argparse
import difflib

from fonetica3.T29 import T29
from fonetica3.vocal_tonica import vocal_tonica
from kaldialign import align, bootstrap_wer_ci, edit_distance


mexbet2kaldi = {
    'V': 'BH', 'D': 'DH', 'G': 'GH', 'x': 'H', 'tS': 'CH', 'Z': 'J',
    'L': 'LJ', 'r(': 'R', 'r': 'RR', 'n~': 'NJ', 'N': 'NG',
    'i_7': 'I1', 'e_7': 'E1', 'a_7': 'A1', 'o_7': 'O1', 'u_7': 'U1',
    'S': 'SH', 'tl': 'TL',  # mx-only phones  # 'j': 'I' ?
}


DIFF_TABLE = """<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
  <title></title>
  <style type="text/css">
    table.diff {{font-family:Courier; border: solid 1px #000000; border-collapse: collapse}}
    .diff_header {{background-color:#e0e0e0; text-align:left; border: solid 1px #000000}}
    td {{border-left: solid 1px #000000; border-right: solid 1px #000000}}
    .diff_ins {{background-color:#aaffaa}}
    .diff_del {{background-color:#ffaaaa}}
    .diff_sub {{background-color:#ffff77}}
  </style>
</head>

<table class=diff>
  <thead class=diff_header>
    <tr>
      <th class=diff_header>Orthography</th>
      <th class=diff_header>Reference pron.</th>
      <th class=diff_header>Hypothesis pron.</th>
    </tr>
  </thead>
  <tbody>{}</tbody>
</table>"""

DIFF_TABLE_ROW = """
    <tr>
      <td>{}</td>
      <td>{}</td>
      <td>{}</td>
    </tr>"""

CHAR_SPAN = "<span class=diff_{}>{}&nbsp;</span>"
BLANK_SPAN = "<span class=diff_{}>&nbsp;&nbsp;</span>"

#def check_phones(pron, ref=kaldi_phones):
#    bad_phones = set(pron) - kaldi_phones
#    assert not bad_phones, bad_phones


def read_lex(lex_path, delim=' '):
    lex = []
    with open(lex_path) as inf:
        for line in inf:
            word, *fields = line.strip().split(delim)
            if delim == '\t':
                # MFA format lexicon
                pron = fields[-1].split()
            elif delim == ' ':
                # ProsodyLab format
                pron = fields
            # for kaldialign.edit_distance
            pron = tuple(pron)
            lex.append((word, pron))
    return lex


def write_lex(lex, lex_path, delim=' '):
    with open(lex_path, 'w') as outf:
        for word, pron in lex:
            outf.write(f"{word}{delim}{' '.join(pron)}\n")


def run_fonetica(test_lex, distincion=False, yeismo=True):
    hyp_prons = []
    for word, ref_pron in test_lex:
        # TODO: running word-by-word fails lenition and nasal assimilation
        # across word boundaries; running in one go fails to assign stress
        # to anything but the last word
        #if ' ' in word:
        #    hyp_pron = ' '.join(T29(vocal_tonica(w), distincion, yeismo)
        #                        for w in word.split())
        #else:
        #    hyp_pron = T29(vocal_tonica(word), distincion, yeismo)
        hyp_pron = T29(vocal_tonica(word), distincion, yeismo)
        pron = hyp_pron.split()
        pron = [mexbet2kaldi.get(p, p).upper() for p in pron if p != '.']
        hyp_pron = tuple(pron)
        hyp_prons.append((word, hyp_pron))
    return hyp_prons


def get_per(ref_prons, hyp_prons):
    # args are like [(word, (p1, p2, ...)), ...]
    ref_prons = [p for w, p in ref_prons]
    hyp_prons = [p for w, p in hyp_prons]
    per = bootstrap_wer_ci(ref_prons, hyp_prons)
    # done manually: this is equivalent
    #results = {'ins': 0, 'del': 0, 'sub': 0, 'total': 0, 'ref_len': 0}
    #for ref, hyp in zip(ref_prons, hyp_prons):
    #    res = edit_distance(ref, hyp)
    #    for k in results:
    #        results[k] += res[k]
    #per = results['total'] / results['ref_len']
    return per


def make_diff_table(ref_prons, hyp_prons, diff_html):
    #writer = difflib.HtmlDiff()
    #refs = [' '.join(p) for w, p in ref_prons]
    #hyps = [' '.join(p) for w, p in hyp_prons]
    with open(diff_html, 'w') as outf:
        #outf.write(writer.make_file(refs, hyps))
        rows = []
        for ref, hyp in zip(ref_prons, hyp_prons):
            orth, ref_pron = ref
            hyp_pron = hyp[1]
            ref_span = ''
            hyp_span = ''
            EPS = '*'
            diff_ali = align(ref_pron, hyp_pron, EPS)
            for ref_sym, hyp_sym in diff_ali:
                if ref_sym == hyp_sym:
                    ref_span += ref_sym + '&nbsp;'
                    hyp_span += hyp_sym + '&nbsp;'
                elif ref_sym == EPS:
                    ref_span += BLANK_SPAN.format('ins')
                    hyp_span += CHAR_SPAN.format('ins', hyp_sym)
                elif hyp_sym == EPS:
                    ref_span += CHAR_SPAN.format('del', ref_sym)
                    hyp_span += BLANK_SPAN.format('del')
                elif hyp_sym != ref_sym:
                    ref_span += CHAR_SPAN.format('sub', ref_sym)
                    hyp_span += CHAR_SPAN.format('sub', hyp_sym)
            rows.append(DIFF_TABLE_ROW.format(orth, ref_span, hyp_span))
        outf.write(DIFF_TABLE.format(''.join(rows)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'region', type=str, choices=['esp', 'latam'], help='region code')
    parser.add_argument(
        'test_lex', type=str, help="test lexicon with reference pronunciations")
    parser.add_argument(
        'hyp_lex', type=str, help="file to write predicted pronunciations")
    parser.add_argument(
        'diff_table', type=str, help="file to write HTML diff table")
    parser.add_argument(
        '--delim', type=str, default=' ', help='lexicon field delimiter')
    args = parser.parse_args()

    test_lex = read_lex(args.test_lex, args.delim)

    if args.region == 'esp':
        distincion = True
        yeismo = False
    elif args.region == 'latam':
        distincion = False
        yeismo = True
    hyp_prons = run_fonetica(test_lex, distincion, yeismo)

    per = get_per(test_lex, hyp_prons)
    print(per)

    write_lex(hyp_prons, args.hyp_lex, args.delim)
    make_diff_table(test_lex, hyp_prons, args.diff_table)
