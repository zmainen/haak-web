---
title: "Olfactory Perception"
slug: olfactory-perception
span: 2001–2017
color: amber
status: completed
themes: [olfaction, perception, decision]
projects:
  - olfactory-bulb
  - olfactory-decisions
  - olfactory-memory
  - covid-olfaction
repos:
  - org: mainenlab
    name: open-olfaction-python
    role: Python module for olfactometer control
  - org: mainenlab
    name: visual-olfactory-vvr
    role: Visual-olfactory virtual linear track
  - org: mainenlab
    name: visual-olfactory-modVVR
    role: Modified virtual VR with visual-olfactory stimuli
---

# Olfactory Perception

Rats can identify an odor in a single sniff. Naoshige Uchida demonstrated this at CSHL by training animals on a two-alternative forced-choice discrimination task and measuring reaction times: as few as 200 milliseconds, one or two sniff cycles, with accuracy already at ceiling (Uchida & Mainen, 2003). Olfactory discrimination operates in the same temporal regime as a visual saccade decision. The program that grew from this result — spanning sixteen years across two institutions — asked how the brain gets from a chemical stimulus to a perceptual commitment that fast, and what that speed reveals about sensory processing in general.

## Sniffing as active sensing

If decisions happen within one or two sniffs, then the sniff itself matters. Adam Kepecs found that sniffing is under precise motor control: rats adjust timing, amplitude, and frequency to match task demands (Kepecs, Uchida & Mainen, 2006, 2007). The sniff functions as a discrete sampling act, analogous to a saccade — a motor event that gates sensory input and sets the timescale of processing. This framework, formalized in a *Chemical Senses* paper and elaborated in *Nature Reviews Neuroscience* (Uchida, Kepecs & Mainen, 2006), connected olfaction to broader theories of active sensing: animals don't passively receive stimuli, they interrogate the world on their own schedule.

## From speed to circuits to computation

The intellectual thread through the neural work was straightforward: if decisions are fast, then the representations driving them must be fast too — so what do they look like, and where?

In the olfactory bulb, Veronica Egger mapped the dendrodendritic circuitry mediating lateral inhibition between mitral and granule cells (Egger et al., 2003, 2005), while Hirac Gurden developed optical imaging of bulbar odor maps (Gurden et al., 2006). These studies characterized the first-order transformation of chemical input. Downstream, Koji Miura recorded from piriform cortex and found that odor representations are sparse, decorrelated across the population, and distributed in a format that supports concentration-invariant recognition (Miura, Mainen & Uchida, 2012; Uchida & Mainen, 2008). The bulb maps odors topographically; piriform recodes them into a format suited for identification regardless of intensity.

The computational counterpart came from Agnieszka Grabska-Barwinska, who built a probabilistic model that can demix overlapping odor mixtures — a problem the olfactory system handles routinely but that had resisted formal treatment (Grabska-Barwinska et al., 2017). The model made explicit what the neural data implied: olfactory cortex performs inference, not just feature detection.

## Deliberation limits and the bridge to confidence

The speed-accuracy tradeoff in olfactory decisions turned out to have a hard boundary. Hatim Zariwala demonstrated that rats reach a deliberation limit — a point beyond which additional sampling time does not improve accuracy — reflecting a computational constraint on evidence accumulation, not a lapse in attention (Zariwala et al., 2013). This was among the first demonstrations of a fixed performance bound in rodent perceptual decision-making.

The olfactory discrimination task also seeded work on decision confidence. If the brain makes fast perceptual commitments, does it also track how reliable those commitments are? Adam Kepecs and Claudia Feierstein carried this question to CSHL, using the same olfactory tasks to build what became the lab's decision-making and confidence program.

## Spatial maps in olfactory cortex

At Champalimaud, Cindy Poo discovered that piriform cortex contains spatial maps — neurons encoding the animal's location during olfactory navigation (Poo et al., 2021, *Nature* 601). Olfactory cortex, conventionally treated as a sensory area, participates in building spatial representations. The finding connected olfaction to hippocampal function and opened a line of work on naturalistic perception that continues in the lab.

## COVID-19 olfactory screening

In 2020, the lab contributed its olfactory psychophysics expertise to international consortia validating self-administered smell tests as rapid screening tools for SARS-CoV-2 infection (Iravani et al., 2020; Snitz et al., 2021).

## People

### CSHL (2000–2007)
- Naoshige Uchida (Postdoc, 2000–2006) — now Prof., Harvard
- Adam Kepecs (Postdoc, 2003–2008) — now Prof., WashU
- Claudia Feierstein (PhD Student, 2001–2007)
- Hatim Zariwala (PhD Student, 2000–2007)
- Matthew Smear (Postdoc, 2006–2008) — now Asst. Prof., U. Oregon
- Dara Sosulski (Research Assistant, 2003–2005)

### Champalimaud (2007–2017)
- Maria Ines Vicente (PhD Student, 2007–2012)
- Hope Johnson (Postdoc, 2009–2012)
- Cindy Poo (PhD Student / Postdoc, 2011–2022) — now Senior Scientist, Allen Institute

### Collaborators
- Koji Miura
- Agnieszka Grabska-Barwińska
- Peter Latham
- Alexandre Pouget

## Key publications

1. Uchida N, Mainen ZF (2003). Speed and accuracy of olfactory discrimination in the rat. *Nat Neurosci* 6, 1224–9.
2. Kepecs A, Uchida N, Mainen ZF (2006). The sniff as a unit of olfactory processing. *Chem Senses* 31, 167–79.
3. Uchida N, Kepecs A, Mainen ZF (2006). Seeing at a glance, smelling in a whiff: rapid forms of perceptual decision-making. *Nat Rev Neurosci* 7, 485–91.
4. Wilson DA, Mainen ZF (2006). Early events in olfactory processing. *Annu Rev Neurosci* 29, 163–201.
5. Kepecs A, Uchida N, Mainen ZF (2007). Rapid and precise control of sniffing during olfactory discrimination in rats. *J Neurophysiol* 98, 205–13.
6. Uchida N, Mainen ZF (2008). Odor concentration invariance by chemical ratio coding. *Front Syst Neurosci* 2, 3.
7. Miura K, Mainen ZF, Uchida N (2012). Odor representations in olfactory cortex: distributed rate coding and decorrelated population activity. *Neuron* 74, 1087–98.
8. Zariwala HA, Kepecs A, Uchida N, Hirokawa J, Mainen ZF (2013). The limits of deliberation in a perceptual decision task. *Neuron* 78, 339–51.
9. Grabska-Barwińska A et al. (2017). A probabilistic approach to demixing odors. *Nat Neurosci* 20, 98–106.
10. Poo C et al. (2022). Spatial maps in piriform cortex during olfactory navigation. *Nature* 601, 595–9.
