---
title: "International Brain Lab"
slug: international-brain-lab
span: 2017–present
color: blue
status: active
themes: [decision, vision, serotonin]
projects:
  - ibl
  - ibl-neuromodulators
repos:
  - org: int-brain-lab
    name: ibllib
    role: IBL core shared libraries
  - org: int-brain-lab
    name: ONE
    role: Open Neurophysiology Environment — data access layer
  - org: int-brain-lab
    name: iblrig
    role: Standardized behavioral rig code
  - org: int-brain-lab
    name: ibl-photometry
    role: Open-source QC toolbox for fiber photometry
  - org: mainenlab
    name: mouse-lsd
    role: Psychedelics extension of IBL platform
---

# International Brain Lab

## The premise

Neuroscience has a reproducibility problem, and it runs deeper than statistics. Laboratories use different tasks, different hardware, different analysis code, and different implicit standards for what counts as a clean dataset. When two labs disagree about a finding, it is usually impossible to tell whether the disagreement is biological or methodological. The International Brain Lab (IBL) was founded in 2017 as a bet that this problem could be solved by construction: define one task, standardize it across 22 laboratories, and use the shared platform to build a brain-wide map of neural activity during decision-making.

Zachary Mainen co-founded the IBL and serves as one of its principal investigators.

## The standardized task

The IBL task is a visual decision: a mouse turns a wheel to indicate which side of the screen a visual stimulus appeared on. It is simple enough to train reliably in every lab, rich enough to engage the full arc of perception, evidence accumulation, and motor execution. Hardware, software, training protocols, and data formats were made identical across all member laboratories (IBL, 2021).

The payoff of that effort was an empirical demonstration that mice trained in different labs, by different experimenters, produce statistically indistinguishable behavioral performance. Standardization, done thoroughly, eliminates the lab-specific confound that shadows most cross-site comparisons in systems neuroscience.

## Brain-wide mapping

With behavior controlled, the IBL recorded from Neuropixels probes across 279 brain regions. The resulting brain-wide map of neural activity during decision-making (IBL, 2024, *Nature*) yielded a clear finding: decision-related signals are distributed across the brain, appearing in regions traditionally associated with sensory processing, motor planning, and internal state regulation alongside the canonical frontal-basal ganglia-collicular circuits.

Charles Findling's analysis of the same dataset uncovered a parallel story for prior expectations. Representations of the animal's learned beliefs about stimulus statistics are spread across many of the same regions (Findling et al., 2024, *Nature*). Prior and evidence signals coexist at the population level, mixed within the same circuits rather than segregated into dedicated modules.

Together, these results reframe the question of where decisions happen. The answer is: broadly, redundantly, and in ways that blur the classical boundaries between sensory, cognitive, and motor processing.

## The lab's contribution: neuromodulation

Within the IBL, the Mainen lab focuses on how neuromodulators shape neural activity during the standardized task. This work takes two forms.

**Fiber photometry survey.** This project records from six neuromodulatory populations (dopamine in VTA and SNc, serotonin in DRN and MRN, norepinephrine in LC, acetylcholine in NBM/SI) during the IBL task. Because the behavior is identical across all recordings, differences between neuromodulatory signals reflect the distinct computational roles of each system — a head-to-head comparison that requires the kind of tight behavioral control the IBL provides.

**Serotonin stimulation + Neuropixels.** Led by Guido Meijer, this project optogenetically activates DRN serotonin neurons during the IBL task while recording brain-wide with Neuropixels probes. The central finding is that serotonin modulates neural dynamics in a subspace orthogonal to the choice-encoding dimensions (Meijer et al., 2025), connecting the IBL platform to the lab's long-running serotonin program.

## Psychedelics extension

The IBL platform makes a specific kind of pharmacological experiment possible. The lab's LSD Neuropixels dataset uses the same task, the same recording infrastructure, and the same analysis pipelines as the normative IBL brain-wide map. This means that when neural dynamics shift under a psychedelic, the comparison is clean: same neurons, same behavioral structure, same analytical framework. Any change in population coding can be attributed to the drug's action on neural circuits rather than to differences in task design or recording methodology. The standardized platform turns a pharmacological perturbation into a controlled experiment on brain-wide computation.

## Infrastructure and data

The IBL's open-science commitment produced infrastructure that outlasts any single dataset. The Open Neurophysiology Environment (ONE) provides standardized data access across the collaboration. A reproducible electrophysiology pipeline handles spike sorting, quality control, and atlas registration. Bimbard et al. (2024) developed an adaptable, reusable chronic Neuropixels implant. All data are publicly released. The lab contributed to the data architecture design (IBL, 2019) and to the development of citric acid water as an alternative to water restriction, reducing the welfare burden of behavioral training (Urai et al., 2021).

## People

### Lab members on IBL
- Guido Meijer (Postdoc, 2018–2024) — serotonin stimulation Neuropixels lead
- Davide Crombie (Postdoc, 2024–present) — neuromodulators photometry lead
- Kcenia Bougrova (PhD Student, 2018–2025) — photometry analysis
- Ines Laranjeira (Technician → PhD Student, 2017–present)
- Laura Freitas-Silva (Technician) — photometry data collection
- Joana Catarino (Technician, 2021–2023) — now at Karolinska
- Bethan Jenkins (Technician, 2025–present) — Neuropixels recordings
- Hélène Duebel (MSc / Fulbright Fellow, 2025)
- Niccolo Bonacchi (Technician, 2008–2017) — data architecture
- Olivier Winter (Technician, 2018–2020) — data architecture
- Julia Huntenburg (Postdoc, 2018–2021)
- Jaime Arlandis (PhD Student, 2020–2025) — LSD extension
- Charline Tessereau (Visiting Scientist, 2025)

### IBL leadership (external)
- Larry Abbott (Columbia)
- Matteo Carandini & Kenneth Harris (UCL)
- Anne Churchland (UCLA)

## Key publications

1. Abbott LF et al. (2017). An International Laboratory for Systems and Computational Neuroscience. *Neuron* 96, 1213–8.
2. IBL (2019). Data architecture and visualization for a large-scale neuroscience collaboration. *bioRxiv* 827873.
3. IBL (2021). A standardized and reproducible method to measure decision-making in mice. *eLife* 10, e63711.
4. Urai AE et al. (2021). Citric acid water as an alternative to water restriction for reward-based behavioral paradigms. *eNeuro*.
5. Ashwood ZC et al. (2022). Mice alternate between discrete strategies during perceptual decision-making. *Nat Neurosci* 25, 201–12.
6. Bimbard C et al. (2024). An adaptable, reusable, and light implant for chronic Neuropixels probes. *eLife* 13, RP98522.
7. Findling C et al. (2024). Brain-wide representations of prior information in mouse decision-making. *Nature*.
8. IBL (2024). A brain-wide map of neural activity during complex behaviour. *Nature*.
9. Meijer GT et al. (2025). Serotonin modulates neural dynamics in a subspace orthogonal to the choice space. *bioRxiv*.
