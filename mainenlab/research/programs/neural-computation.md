---
title: "Neural Computation & Reliability"
slug: neural-computation
span: 1990–2006
color: slate
status: completed
themes: [biophysics, synaptic, dendritic, spike]
projects:
  - hippo-dendrites
  - spike-reliability
  - kinetic-models
  - synaptic-plasticity
  - olfactory-bulb
  - barrel-cortex
repos: []
---

# Neural Computation & Reliability

Every component of a neuron — ion channels, synapses, the dendritic tree — is stochastic. Yet neurons produce precisely timed outputs. The first decade of the lab's work traced how reliable computation emerges from unreliable parts, and how the physical structure of a neuron determines its computational role.

## Dendritic computation in hippocampus

Computational models built from three-dimensional reconstructions of CA1 pyramidal neurons found that dendritic geometry determines which patterns of synaptic input drive a neuron to fire. The electrotonic architecture of the dendrite interacts with Hebbian learning rules to produce self-organized feature maps — the tree's branching pattern shapes what the neuron can learn (Brown, Mainen, Zador & Claiborne, 1991–1993; Mainen et al., 1996).

## Spike reliability and dendritic structure

The central result came at the Salk Institute. Intracellular recordings from neocortical neurons found that spike timing is reliable in response to fluctuating inputs — the same current injection produces the same spike times, trial after trial — but unreliable in response to constant inputs (Mainen & Sejnowski, 1995). Reliability depends on the temporal structure of the input, not on some intrinsic property of the cell.

A separate line of work found that dendritic morphology is the primary determinant of a neuron's firing pattern (Mainen & Sejnowski, 1996). Pyramidal neurons fire regularly or in bursts depending on their dendritic geometry, not their ion channel composition. A biophysical model of spike initiation formalized this: the axon initial segment, not the soma, is the site of spike initiation in neocortical pyramidal neurons (Mainen et al., 1995).

Together, these results reframed the relationship between structure and function in single neurons. Dendritic morphology determines firing pattern, input statistics determine reliability, and the interaction of the two produces the computational identity of the cell.

## Kinetic models of synapses and channels

In parallel, a long collaboration with Alain Destexhe produced a family of kinetic models for synaptic receptors (AMPA, NMDA, GABA-A, GABA-B) and neuromodulatory systems (Destexhe, Mainen & Sejnowski, 1994–1998). The models captured receptor binding and unbinding kinetics with enough biophysical detail to reproduce experimental data, but ran fast enough for network-scale simulations. They became standard tools in computational neuroscience.

## Synaptic plasticity and two-photon imaging

Two-photon imaging of individual dendritic spines found that NMDA receptors at single synapses are not saturated during transmission (Mainen et al., 1999). Because each synapse operates below saturation, the gain of each synapse can be independently tuned by experience — a prerequisite for synapse-specific plasticity.

This period also produced methods for two-photon calcium imaging and for estimating intracellular calcium concentrations without wavelength ratioing (Mainen et al., 1999; Maravall et al., 2000).

## Olfactory bulb circuits

The spike reliability work raised a question the neocortical preparation could not answer: how does unreliable cellular machinery support fast, accurate sensory discrimination in a behaving animal? The olfactory bulb offered a tractable circuit — a two-synapse path from receptor to cortex — where the transformation from sensory input to neural code could be followed in detail.

Veronica Egger's recordings from dendrodendritic synapses between mitral and granule cells identified the mechanisms of lateral inhibition in the bulb: local calcium signals in granule cell spines mediate reciprocal inhibition without requiring action potentials (Egger, Svoboda & Mainen, 2003, 2005). Hirac Gurden developed intrinsic optical imaging of odor-evoked activity across the bulb surface (Gurden, Uchida & Mainen, 2006).

This circuit-level work set the stage for the next program. When Naoshige Uchida joined the lab and asked how fast rats can discriminate odors, the question connected cellular biophysics to perception and decision-making.

## People

### PhD — Yale (1990–1993)
- Tom Brown (advisor)
- Anthony Zador (fellow student) — now PI, CSHL
- Brenda Claiborne (collaborator)

### PhD — Salk Institute (1993–1996)
- Terry Sejnowski (advisor)
- Alain Destexhe (collaborator) — now Director of Research, CNRS

### Postdoc — CSHL / Salk (1996–1999)
- Roberto Malinow (mentor) — now Prof., UCSD
- Karel Svoboda (collaborator) — now at Janelia / Allen Institute

### Independent — CSHL (1999–2006)
- Steve Macknik (Postdoc, 1999–2001) — now Prof., SUNY Downstate
- Veronica Egger (Postdoc, 2000–2004) — now Prof., Regensburg University
- Naoshige Uchida (Postdoc, 2000–2006) — now Prof., Harvard
- Hirac Gurden (Postdoc, 2000–2005)
- Michael Quirk (Postdoc, 2001–2006)
- Claudia Feierstein (PhD Student, 2001–2007)
- Dara Sosulski (Research Assistant, 2003–2005)
- Hatim Zariwala (PhD Student, 2000–2007)

## Key publications

1. Mainen ZF, Sejnowski TJ (1995). Reliability of spike timing in neocortical neurons. *Science* 268, 1503–6.
2. Mainen ZF, Joerges J, Huguenard JR, Sejnowski TJ (1995). A model of spike initiation in neocortical pyramidal neurons. *Neuron* 15, 1427–39.
3. Mainen ZF, Sejnowski TJ (1996). Influence of dendritic structure on firing pattern in model neocortical neurons. *Nature* 382, 363–6.
4. Mainen ZF, Carnevale NT, Zador AM, Claiborne BJ, Brown TH (1996). Electrotonic architecture of hippocampal CA1 pyramidal neurons. *J Neurophysiol* 76, 1904–23.
5. Destexhe A, Mainen ZF, Sejnowski TJ (1994). Synthesis of models for excitable membranes, synaptic transmission, and neuromodulation using a common kinetic framework. *J Comput Neurosci* 1, 195–230.
6. Destexhe A, Mainen ZF, Sejnowski TJ (1994). An efficient method for computing synaptic conductances based on a kinetic model of receptor binding. *Neural Comput* 6, 14–18.
7. Mainen ZF, Malinow R, Svoboda K (1999). Synaptic calcium transients in single spines indicate that NMDA receptors are not saturated. *Nature* 399, 151–5.
8. Maravall M, Mainen ZF, Sabatini BL, Svoboda K (2000). Estimating intracellular calcium concentrations and buffering without wavelength ratioing. *Biophys J* 78, 2655–67.
9. Egger V, Svoboda K, Mainen ZF (2003). Mechanisms of lateral inhibition in the olfactory bulb. *J Neurosci* 23, 7551–8.
10. Egger V, Svoboda K, Mainen ZF (2005). Dendrodendritic synaptic signals in olfactory bulb granule cells. *J Neurosci* 25, 3521–30.
