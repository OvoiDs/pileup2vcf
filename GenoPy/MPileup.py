#!/usr/bin/env python
# encoding: utf-8

'''
Created on 3 août 2015

@author: boursin
'''

#from matplotlib import pyplot as plt
#from matplotlib import collections as mc
#from Bio.Statistics.lowess import lowess
from collections import OrderedDict, deque
from GenoPy.Genomic import *
from GenoPy.Variants import *
#from GenoPy.Segmentation import pelt
import pyfaidx
import sys


###############################################################################
###########################  MPILEUP Class  ###################################
###############################################################################

class MPileup(object):
    '''MPileup class
    This class takes charge of mpileup files. It is in charge of parsing each line of the mpileup file and
    create Variant objects'''
    def __init__(self, file, dph, io, parameters, bed=None):
        self.log = io.log
        self.parameters = parameters
        self.bed = bed
        self.file = file # io.getIO('mpileup')
        self.dph = dph
        self.arrayPileup = []
        
        self.wroteHeader = False
        self.fasta = pyfaidx.Fasta(parameters['refGenome'])
        self.indelsToAddToVCF = []

    def getContextFromPosition(self, chr, pos, howMuchNucleotides=4):
        '''Returns flanking nucleotides for coordinates'''
        pos = int(pos)
        boundaries = (pos - howMuchNucleotides, pos + howMuchNucleotides)
        #if (boundaries[0] not in self.fasta[chr] or boundaries[1] not in self.fasta[chr]):
        #    return None
        return self.fasta[chr][boundaries[0]:boundaries[1]]

    # Fonction permettant de parser le fichier mpileup et de définir pour chaque ligne un objet variant. Cet objet est ammené à être callé ou non lors de l'étape
    # getFilterState. Si passFilter = cur.getFilterState() = True, alors on a affaire à un variant.
    def parse(self):
        '''This takes as input the mpileup file and parses it. It has disparate functions, but this is the data provider function.
        * Returns: self.arrayPileup
        '''
        avancement = []
        alreadyPrinted = False
        lineCounter = 0
        skipped = 0
        for line in self.file:
            lineCounter += 1
            try:
                #with line.split('\t') as elem:
                elem = line.split('\t')
                chr = elem[0].strip().rstrip('\n').rstrip('\t')
                pos = int(elem[1].strip().rstrip('\n').rstrip('\t'))
                refNuc = elem[2].strip().rstrip('\n').rstrip('\t').upper()
                depth = int(elem[3].strip().rstrip('\n').rstrip('\t'))
                sequence = elem[4].strip().rstrip('\n').rstrip('\t')
                quality = elem[5].strip().rstrip('\n').rstrip('\t')
                mapQual = elem[6].strip().rstrip('\n').rstrip('\t')
                posInRead = elem[7].strip().rstrip('\n').rstrip('\t').split(',')
                #print len(posInRead), len(mapQual), len(quality)
                # Assertions
                #assert (len(mapQual) == len(quality)), "Weird formating: mapping quality track length is not the same as nucleotide quality track length"
                #assert (len(quality) == len(posInRead)), "Weird formating: nucleotide quality track length is not the same as position in read track length"
                #assert (len(refNuc) == 1), "Weird formating: there is {} nucleotide at this position !".format(len(refNuc))
            
            except:
                print 'CrashDump:'
                print line
                print [len(x) for x in elem]
                raise MpileupFormatError("Cannot initialize at line {}.\n Please check that your Mpileup file has 8 columns and has been generated with mapping quality and base position in read using samtools 0.1.18 (further versions seems to suffer from bugs).\n MPileup with good format might be generated using: samtools mpileup -A -s -O -B -f ../Pileup2VCF/hg19/hg19.fa 208204422-ADN-2_S2_L001.bam".format(lineCounter))
            if depth == 0:
                #print "Unsequenced region at {}-{}".format(chr, pos)
                continue
            if not chr in avancement:
                self.dph.walk(Chromosome=chr)
                avancement.append(chr)
                before = elem[1]
                self.log("Parsing and calling on {0}".format(chr))
            curPos = Position(chr, pos, quality, mapQual, depth, refNuc, pos_before=before, bed=self.bed)
            if not curPos.inBed and self.parameters['onlyBed']:
                skipped += 1
                continue
            if (lineCounter % 500 == 0):
                percents = float(lineCounter) * 100 / float(self.parameters['lineNb'])
                self.log("Parsed around {0:.2f}% of the file ({1} line read / {2} total)".format(percents, lineCounter, self.parameters['lineNb']), loglevel=3)
            context = self.getContextFromPosition(chr, pos)
            biggerContext = self.getContextFromPosition(chr, pos, howMuchNucleotides=100)
            if (int(depth) > 0):
                
                self.dph.add(chr, pos, curPos)
                before = pos
            # Création d'un object contenant la ligne et pouvant accueillir un éventuel variant
            cur = Variant(chr, pos, refNuc, depth, sequence, quality, mapQual, self.parameters, context, biggerContext)
            #print cur
            cur.getInfos()
            if cur.isVariant() is True:
                #print cur
                self.arrayPileup.append(cur)
            # A ce stade, on enregistre tous les objets variants en se basant uniquement sur la présence éventuelle d'un nucléotide non ref. Le problème de cette méthode est qu'elle
            # peut entrainer beaucoup de variants selon la qualité du séquençage...
            # On verra bien ce que cela donne. L'étape suivante est
        self.dph.writeDepthProfile() # We write the last positions in depthProfile before returning
        self.log("Skipped {} positions as they were not in Bed.".format(skipped), loglevel=2)
        return UnclassifiedVariantCollection(self.arrayPileup, self.parameters)
    
