from sqlite3 import Connection

import pandas as pd
import re


def calc_boxplot(vals):
    vals = [float(x) for x in vals if x != 'NA']
    pepdf = pd.DataFrame(dict(boxvals=vals))
    q1 = pepdf.boxvals.quantile(0.25)
    q2 = pepdf.boxvals.quantile(0.5)
    q3 = pepdf.boxvals.quantile(0.75)
    iqr = q3 - q1
    return {'q1': q1, 'q2': q2, 'q3': q3,
            'upper': q3 + 1.5 * iqr, 'lower': q1 - 1.5 * iqr}


def calc_longitudinal_qc(infiles):
    qcmap = {'miscleav': {}}
    qcpsms = []
    con = Connection(infiles['sqltable'])
    qcmap['nr_psms'] = {'scans':
                        con.execute('SELECT COUNT(*) FROM mzml').fetchone()[0]}
    psms = parse_psms(infiles['psmtable'], is_instrument_qc=True)
    header = next(psms)
    perrorix = header.index('PrecursorError(ppm)')
    qvalix = header.index('QValue')
    msgfix = header.index('MSGFScore')
    rtix = header.index('Retention time(min)')
    misclix = header.index('missed_cleavage')
    for line in psms:
        # FIXME filtering in galaxy? will be incorrect num of peptides
        if float(line[qvalix]) > 0.01:
            continue
        qcpsms.append(line)
        if int(line[misclix]) < 4:
            try:
                qcmap['miscleav'][line[misclix]] += 1
            except KeyError:
                qcmap['miscleav'][line[misclix]] = 1
    qcmap['perror'] = calc_boxplot([psm[perrorix] for psm in qcpsms])
    qcmap['msgfscore'] = calc_boxplot([psm[msgfix] for psm in qcpsms])
    qcmap['rt'] = calc_boxplot([psm[rtix] for psm in qcpsms])
    qcmap['nr_psms']['psms'] = len(qcpsms)
    peps = []
    with open(infiles['peptable']) as fp:
        header, lines = table_reader(fp)
        areaix = header.index('MS1 area (highest of all PSMs)')
        protix = header.index('Protein(s)')
        count = 0
        unicount = 0
        for line in lines:
            count += 1
            if ';' not in line[protix]:
                unicount += 1
            try:
                peps.append(line)
            except ValueError:
                pass
    qcmap['peparea'] = calc_boxplot([x[areaix] for x in peps])
    qcmap['nr_peptides'] = {'peptides': count, 'unique_peptides': unicount}
    with open(infiles['prottable']) as fp:
        # FIXME may need to filter proteins on FDR
        # first line is header
        qcmap['nr_proteins'] = {'proteins': sum(1 for _ in fp) - 1}
    return qcmap


def parse_header(oldheader):
    header = ['Biological set', 'Retention time(min)', 'PrecursorError(ppm)',
              'Peptide', 'MSGFScore', 'QValue', 'percolator svm-score',
              'MS1 area', 'Fractions', 'Delta pI',
              'tmt6plex_126',
              'tmt6plex_127',
              'tmt6plex_128',
              'tmt6plex_129',
              'tmt6plex_130',
              'tmt6plex_131',
              'tmt10plex_126',
              'tmt10plex_127N',
              'tmt10plex_127C',
              'tmt10plex_128N',
              'tmt10plex_128C',
              'tmt10plex_129N',
              'tmt10plex_129C',
              'tmt10plex_130N',
              'tmt10plex_130C',
              'tmt10plex_131',
              'tmt11plex_126',
              'tmt11plex_127N',
              'tmt11plex_127C',
              'tmt11plex_128N',
              'tmt11plex_128C',
              'tmt11plex_129N',
              'tmt11plex_129C',
              'tmt11plex_130N',
              'tmt11plex_130C',
              'tmt11plex_131N',
              'tmt11plex_131C',
              'itraq8plex_113',
              'itraq8plex_114',
              'itraq8plex_115',
              'itraq8plex_116',
              'itraq8plex_117',
              'itraq8plex_118',
              'itraq8plex_119',
              'itraq8plex_120',
              'itraq8plex_121',
              ]
    newheader, colnrs = [], []
    for field in header:
        try:
            colnrs.append(oldheader.index(field))
        except ValueError:
            # happens when not running hirief, TMT, e.g.
            pass
        else:
            newheader.append(field)
    return newheader + ['Plate_ID', 'missed_cleavage'], colnrs


def parse_psms(infile, is_instrument_qc=False, platepatterns=False):
    with open(infile) as fp:
        oldheader = next(fp).strip('\n').split('\t')
        pepseqcol = oldheader.index('Peptide')
        newheader, colnrs = parse_header(oldheader)
        yield newheader
        if not is_instrument_qc:
            biosetcol = oldheader.index('Biological set')
        fncol = oldheader.index('#SpecFile')
        for line in fp:
            line = line.strip('\n').split('\t')
            plate_id = 'NA'
            if not is_instrument_qc:
                plate_id = get_plate_id(line[biosetcol], line[fncol],
                                        platepatterns)
            yield [line[x] for x in colnrs] + [
                plate_id, str(count_missed_cleavage(line[pepseqcol]))]


def get_plate_id(bioset, fn, patterns):
    for pattern in patterns:
        if pattern in fn:
            return '{}_{}'.format(bioset, pattern)
    print('Could not match patterns {} to filename {} to detect '
          'name of plate, substitute with NA'.format(patterns, fn))
    return '{}_{}'.format(bioset, 'NA')


def count_missed_cleavage(full_pepseq, count=0):
    '''Regex .*[KR][^P] matches until the end and checks if there is a final
    charachter so this will not match the tryptic residue'''
    pepseq = re.sub('[\+\-]\d*.\d*', '', full_pepseq)
    match = re.match('.*[KR][^P]', pepseq)
    if match:
        count += 1
        return count_missed_cleavage(match.group()[:-1], count)
    else:
        return count


def table_reader(fp):
    header = next(fp).strip('\n').split('\t')
    lines = (line.strip('\n').split('\t') for line in fp)
    return header, lines
