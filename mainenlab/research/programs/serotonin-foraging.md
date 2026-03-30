---
title: "Serotonin & Foraging"
slug: serotonin-foraging
span: 2007–present
color: teal
status: active
themes: [serotonin, decision, embodiment, perception]
projects:
  - 5ht-electrophysiology
  - 5ht-optogenetics
  - 5ht-circuits
  - computational-decisions
  - 5ht-neuropixels
  - face-decoding
repos:
  - org: mainenlab
    name: human-foraging
    role: Human behavioral task (browser-based probabilistic foraging)
  - org: mainenlab
    name: hidden_state_task
    role: Gamified inference task ("Schrödinger Shooting", Godot)
  - org: mainenlab
    name: 5HT-Development
    role: Analysis code for mPFC–DRN maturation study
---

# Serotonin & Foraging

## A molecule without a theory

Serotonin has been linked to mood, appetite, sleep, aggression, and reward, yet no single framework explains why one molecule does so many things. For decades, the field managed this problem by partitioning: clinical researchers studied depression, pharmacologists studied receptor subtypes, systems neuroscientists studied reward prediction. Each community had a piece, none had the whole. Our program started from the position that the missing ingredient was empirical: record from serotonin neurons in behaving animals and ask what they actually encode.

## Encoding: what serotonin neurons respond to

Sachin Ranade's recordings from dorsal raphe nucleus (DRN) serotonin neurons in behaving mice established that these neurons encode a diverse set of events: sensory stimuli, motor actions, and rewards, each with distinct temporal profiles (Ranade & Mainen, 2009). The responses were precise and event-locked, not the slow, diffuse mood signals that textbook accounts had suggested. Guillaume Dugué then developed optogenetic tools for selective activation and silencing of DRN serotonin neurons, establishing the technical foundation that every subsequent study in the program would build on (Dugué et al., 2014).

## Function: patience, persistence, flexibility

With the ability to both record and manipulate serotonin neurons, the next question was functional: what happens when you turn them on or off during behavior?

The answer came in stages. Madalena Fonseca and Masayoshi Murakami demonstrated that optogenetic activation of DRN serotonin neurons promotes waiting: animals persist longer at a task when serotonin neurons are active (Fonseca et al., 2015). Patricia Correia identified parallel effects on locomotion, where phasic serotonin activation transiently inhibits movement and then facilitates it over longer timescales (Correia et al., 2017). Sara Matias, recording during a probabilistic reversal task, observed that serotonin neuron activity tracks the moments when the world changes and behavior needs to change with it (Matias et al., 2017).

A picture emerged: serotonin regulates the balance between persistence and flexibility. It tells the brain how long to keep doing what it's doing.

## Foraging: the setting where persistence matters most

If serotonin governs persistence, then foraging is where that governance is most consequential. The core foraging decision is how long to exploit a depleting resource before moving on. Eran Lottem designed a probabilistic foraging task for mice and demonstrated that optogenetic activation of serotonin neurons during foraging promotes active persistence: animals stay longer at reward sites, and this effect is specific to active engagement, not passive waiting (Lottem et al., 2018). Dhruba Banerjee, Pietro Vertechi, Dario Sarra, and Matthijs oude Lohuis contributed to this work.

The program shifted from "what do serotonin neurons encode?" to "how does serotonin shape decisions in ecologically meaningful contexts?"

## Hidden states: foraging as inference

Vertechi, Lottem, and Sarra then asked a deeper question: what computation underlies the decision to stay or leave? Their answer was that foraging mice perform inference over hidden states. Animals estimate whether the environment has changed, integrating reward history against a generative model of the task rather than applying a simple reward-tracking rule (Vertechi et al., 2020). Using lesions and recordings, they showed that orbitofrontal and medial prefrontal cortex make distinct contributions to this inference. The foraging task became a tool for studying how brains represent and update beliefs under uncertainty.

The human version of this task, built by Tiago Quendera as a browser-based game, confirmed that human subjects use similar inference strategies.

## Circuit maturation: how persistence develops

In parallel, Nicolas Gutierrez-Castellanos discovered that the prefrontal input to DRN matures postnatally. The circuit that controls serotonergic modulation of persistence is not present at birth but develops over weeks (Gutierrez-Castellanos, Sarra, Godinho & Mainen, 2024, published in eLife after an earlier preprint). This added a developmental dimension: the capacity for adaptive persistence is something the brain has to build.

## The reservoir: brain-wide decision variables

Fanny Cazettes, collaborating with Alfonso Renart, undertook large-scale Neuropixels recordings during foraging and uncovered a distributed reservoir of decision-relevant variables across the brain. An earlier study by Cazettes with Davide Reato and Renart had already shown that serotonin activation drives pupil-linked arousal in a manner consistent with state uncertainty signaling (Cazettes et al., 2021). The Neuropixels work extended this: surprise, reward history, confidence, and other task-related signals coexist in neural populations spanning many regions simultaneously (Cazettes et al., 2023). Foraging decisions are not localized to prefrontal cortex; they can be read out from population activity across the brain, in a format that is robust and redundant.

## The face: cognitive readout, and what it implies for mechanism

The most unexpected turn came next. Cazettes, working with Reato, Elisabete Augusto, and Renart, showed that the same latent cognitive variables readable from neural populations are also readable from the mouse's face (Cazettes et al., 2025). Facial expressions in mice track surprise, confidence, and engagement, reflecting ongoing computation rather than simple affective states. If the brain's internal variables leak to the face, facial dynamics become a non-invasive assay for cognitive state, one that scales to humans.

That link between internal variables and external readout raised a mechanistic question: how does serotonin modulate ongoing brain dynamics without disrupting the computations they support?

## Orthogonal modulation: serotonin's mechanism

Guido Meijer's brain-wide Neuropixels recordings during serotonin stimulation provided an answer. Serotonin modulates neural dynamics in a subspace orthogonal to the dimensions encoding choice (Meijer et al., 2025). It shifts brain state without corrupting the decision process itself. This explains how a single neuromodulator can alter persistence, flexibility, and arousal while leaving the content of decisions intact.

## Where the program is going

The work now extends along two lines that grow from the same root. One asks how serotonin interacts with novelty during foraging, testing whether the circuitry that governs persistence also mediates responses to unexpected events, and whether a computational framework based on state prediction error can unify the persistence, flexibility, and novelty findings. The other translates the face-decoding approach to humans, using VR foraging tasks with eye tracking and facial recording to ask whether human facial dynamics carry the same cognitive information identified in mice, and whether these signals can characterize individual differences in cognition.

## People

### Founders and leads
- **Zachary Mainen** — Principal investigator (2007–present)
- **Alfonso Renart** — Co-PI on the Cazettes series (pupil, reservoir, face) and human translation

### Phase 1: Encoding and tools (2007–2014)
- Sachin Ranade (PhD student, CSHL → Champalimaud)
- Guillaume Dugué (Postdoc) — now PI, Collège de France / CNRS
- Masayoshi Murakami (Postdoc)
- Magor Lőrincz (Postdoc) — now PI, U. Szeged

### Phase 2: Function and foraging (2013–2021)
- Sara Matias (PhD student)
- Patricia Correia (PhD student)
- Eran Lottem (Postdoc)
- Madalena Stilwell Fonseca (PhD student)
- Pietro Vertechi (PhD student)
- Dario Sarra (PhD student)
- Dhruba Banerjee (Postdoc)
- Matthijs oude Lohuis (Postdoc, 2018–2020)
- Tiago Quendera (PhD student)

### Phase 3: Circuits, reservoir, and face (2016–2025)
- Nicolas Gutierrez-Castellanos (Postdoc)
- Beatriz Godinho (MSc student)
- Fanny Cazettes (Postdoc) — now tenured researcher, CNRS
- Davide Reato (Postdoc) — pupil arousal and face decoding (Cazettes 2021, 2025)
- Elisabete Augusto (Postdoc)
- Joana Catarino (Technician) — now at Karolinska

### Phase 4: Mechanism and translation (2018–present)
- Guido Meijer (Postdoc)
- Solène Sautory (PhD student)
- Ines Laranjeira (PhD student)
- Laura Freitas-Silva (Technician)
- Stefan Hajduk (MSc student)
- Félix Hubert (Postdoc, U. Geneva — collaborator)
- Romain Ligneul (Postdoc) — now PI, INSERM
- Raphael Steinfeld (Postdoc)

## Key publications

1. Ranade SP, Mainen ZF (2009). Transient firing of dorsal raphe neurons encodes diverse and specific sensory, motor, and reward events. *J Neurophysiol* 102, 3026–37.
2. Dugué GP et al. (2014). Optogenetic recruitment of dorsal raphe serotonergic neurons acutely decreases mechanosensory responsivity in behaving mice. *PLoS ONE* 9, e105941.
3. Fonseca MS, Murakami M, Mainen ZF (2015). Activation of dorsal raphe serotonergic neurons promotes persistent waiting. *Curr Biol* 25, 306–15.
4. Lottem E, Lőrincz ML, Mainen ZF (2016). Optogenetic activation of dorsal raphe serotonin neurons rapidly inhibits spontaneous but not odor-evoked activity in olfactory cortex. *J Neurosci* 36, 7–18.
5. Matias S, Lottem E, Dugué G, Mainen ZF (2017). Activity patterns of serotonin neurons underlying cognitive flexibility. *eLife* 6, e20552.
6. Correia PA et al. (2017). Transient inhibition and long-term facilitation of locomotion by phasic optogenetic activation of serotonin neurons. *eLife* 6, e20975.
7. Lottem E, Banerjee D, Vertechi P, Sarra D, oude Lohuis M, Mainen ZF (2018). Activation of serotonin neurons promotes active persistence in a probabilistic foraging task. *Nat Commun* 9, 1000.
8. Vertechi P, Lottem E, Sarra D, Godinho B, Treves I, Quendera T, oude Lohuis MN, Mainen ZF (2020). Inference-based decisions in a hidden state foraging task. *Neuron* 106, 166–76.
9. Cazettes F, Reato D, Morais JP, Renart A, Mainen ZF (2021). Phasic activation of dorsal raphe serotonergic neurons increases pupil-linked arousal. *Curr Biol* 31, 192–7.
10. Gutierrez-Castellanos N, Sarra D, Godinho BS, Mainen ZF (2024). Maturation of prefrontal input to dorsal raphe increases behavioral persistence in mice. *eLife*.
11. Cazettes F, Mazzucato L, Murakami M, Morais JP, Augusto E, Renart A, Mainen ZF (2023). A reservoir of foraging decision variables in the mouse brain. *Nat Neurosci*.
12. Ligneul R, Mainen ZF (2023). Serotonin. *Curr Biol* 33, R1209–R1221.
13. Cazettes F, Reato D, Augusto E, Renart A, Mainen ZF (2025). Facial expressions in mice reveal latent cognitive variables. *Nat Neurosci*.
14. Meijer GT et al. (2025). Serotonin modulates neural dynamics in a subspace orthogonal to the choice space. *bioRxiv*.
