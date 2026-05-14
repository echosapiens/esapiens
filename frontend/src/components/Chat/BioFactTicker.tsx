import { useState, useEffect, useCallback } from 'react';

/* ── 30+ bioinformatics facts ── */
const FACTS: string[] = [
  'The human genome contains approximately 3.2 billion base pairs, yet only about 1.5% codes for proteins.',
  'E. coli can replicate its 4.6 Mbp genome in under 40 minutes under optimal conditions.',
  'The longest human gene, DMD (dystrophin), spans 2.4 million base pairs on chromosome X.',
  'A single gram of DNA can theoretically store 215 petabytes of data.',
  'The yeast Saccharomyces cerevisiae was the first eukaryotic genome sequenced, in 1996.',
  'Humans share roughly 98.7% of their DNA with chimpanzees and about 60% with bananas.',
  'The ENCODE project found that at least 80% of the human genome has biochemical activity.',
  'NGS read lengths have grown from 35 bases (Solexa, 2006) to over 10,000 bases (PacBio HiFi).',
  'A typical human somatic cell contains about 6 picograms of DNA.',
  'The proteome of Homo sapiens comprises over 20,000 protein-coding genes, yielding an estimated 80,000+ proteoforms after splicing and modification.',
  'Mass spectrometry can now identify over 10,000 proteins from a single tissue sample.',
  'PhiX174 was the first DNA genome ever sequenced, all 5,386 bases, by Fred Sanger in 1977.',
  'The Tara Oceans expedition cataloged over 44 million microbial genes across ocean samples worldwide.',
  'P53 is mutated in over 50% of human cancers, making it the most studied tumor suppressor gene.',
  'The average protein is 300-400 amino acids long, but titin spans over 33,000 residues.',
  'CRISPR-Cas9 was adapted from a natural bacterial immune system discovered in Streptococcus thermophilus.',
  'Each human cell repairs roughly 10,000 DNA lesions per day through base excision repair alone.',
  'RNA sequencing (RNA-seq) can quantify expression of over 20,000 genes in a single experiment.',
  'The pangenome of Streptococcus agalactiae contains more than twice the genes of any single strain.',
  'AlphaFold2 predicted structures for over 200 million proteins, covering virtually every known UniProt entry.',
  'The Human Cell Atlas aims to map every cell type in the human body across all 37 trillion cells.',
  'Telomeres shorten by approximately 50-200 bases per cell division, acting as a mitotic clock.',
  'Mitochondrial DNA is inherited maternally and mutates roughly 10 times faster than nuclear DNA.',
  'A single run on an Illumina NovaSeq X can produce over 16 terabases of sequence data.',
  'The Notch signaling pathway is one of the most ancient, conserved from jellyfish to humans.',
  'Epigenetic modifications can alter gene expression without changing the underlying DNA sequence.',
  'The KEGG database catalogs over 18,000 metabolic and signaling pathways across organisms.',
  'Alternative splicing allows the roughly 20,000 human genes to produce over 100,000 distinct mRNA transcripts.',
  'The average bacterial genome is about 3-4 Mbp, while the largest known viral genome (Pandoravirus) exceeds 2.5 Mbp.',
  'Ribosomal RNA genes (rDNA) exist in roughly 300-400 copies in the human genome.',
  'Single-cell ATAC-seq can measure chromatin accessibility in over 1 million individual cells per experiment.',
  'Proteins fold in milliseconds to seconds, but brute-force computational folding of even small proteins took years before deep learning approaches.',
  'Horizontal gene transfer accounts for an estimated 80% of gene content in some prokaryotic genomes.',
  'The human microbiome encodes over 3 million distinct genes, outnumbering human genes 150 to 1.',
  'Gene ontology annotations currently describe over 45,000 terms across biological process, molecular function, and cellular component.',
];

interface BioFactTickerProps {
  /** Auto-advance interval in milliseconds; default 8000 */
  intervalMs?: number;
}

export function BioFactTicker({ intervalMs = 8000 }: BioFactTickerProps) {
  const [index, setIndex] = useState(() => Math.floor(Math.random() * FACTS.length));
  const [fade, setFade] = useState(true);

  const advance = useCallback(() => {
    setFade(false);
    setTimeout(() => {
      setIndex((i) => (i + 1) % FACTS.length);
      setFade(true);
    }, 350);
  }, []);

  useEffect(() => {
    const timer = setInterval(advance, intervalMs);
    return () => clearInterval(timer);
  }, [advance, intervalMs]);

  return (
    <div
      onClick={advance}
      style={{
        cursor: 'pointer',
        padding: '10px 14px',
        minHeight: 72,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
      }}
    >
      <span
        style={{
          fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
          fontSize: '0.55rem',
          fontWeight: 700,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: 'var(--e-accent-cyan, #0891B2)',
          marginBottom: 5,
        }}
      >
        Did you know?
      </span>
      <p
        style={{
          fontFamily: 'var(--e-font-sans, Inter, sans-serif)',
          fontSize: '0.8rem',
          lineHeight: 1.55,
          color: 'var(--e-text-secondary, #525252)',
          margin: 0,
          opacity: fade ? 1 : 0,
          transition: 'opacity 350ms ease',
        }}
      >
        {FACTS[index]}
      </p>
    </div>
  );
}