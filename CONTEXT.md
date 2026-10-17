# 3D Scene Understanding

Turns RGB photos or a short video of one room into a metric 3D Scene with open-vocabulary Objects, spatial Relations and grounded question answering.

## Language

### Capture

**Scene**:
One captured room and the understanding derived from its capture.
_Avoid_: room (for the record), project

**Frame**:
One image from a photo capture or a moment in a video.
_Avoid_: photo, picture

**Keyframe**:
A Frame selected as useful for understanding the Scene.
_Avoid_: selected image

**Workspace**:
The working inputs and derived artifacts belonging to one Scene.
_Avoid_: scene folder, scene directory

### Processing

**Job**:
One request to process a Scene through all of its Stages.
_Avoid_: run, task, pipeline run

**Stage**:
One named transformation in the Scene processing sequence (ingest, recon, align, mesh, segment, lift, embed, attributes, graph).
_Avoid_: step, phase

**Algorithm**:
A chosen method for performing a Stage, registered under a `<stage>.<method>` name.
_Avoid_: model, plugin

**Manifest**:
A summary describing the artifacts and outcome produced by a Stage.
_Avoid_: metadata, result

**Stage Run**:
The record of a Stage within a Scene's latest Job, identifying its Algorithm and settings.
_Avoid_: run

**Vocabulary**:
The set of concepts available for naming detected things.
_Avoid_: label list, prompts

**Publication**:
Copying a finished Scene Graph and its Object embeddings into the database, after which the Scene is ready.
_Avoid_: import, sync

### Compute

**Target**:
A place where an Algorithm executes: in-process on the worker or a GPU host behind the compute contract.
_Avoid_: GPU worker, backend, provider

**Compute Run**:
One execution of an Algorithm on a compute Target.
_Avoid_: run, remote job

### Understanding

**Instance**:
A thing distinguished from other things across captured views, with a stable identity.
_Avoid_: detection, mask, cluster

**Object**:
An Instance enriched with its spatial extent, labels and attributes; its identity is unchanged.
_Avoid_: item, entity

**Relation**:
A spatial connection between Objects, or between an Object and the room.
_Avoid_: edge, link

**Scene Graph**:
The Objects and Relations describing a Scene.
_Avoid_: graph (bare), layout

## Relationships

- A **Scene** has at most one active **Job**; a **Job** runs every **Stage** in order, one **Compute Run** each, all on one **Target**.
- Each **Stage** is performed by exactly one configured **Algorithm** and leaves one **Manifest** and one **Stage Run**.
- Each **Instance** becomes exactly one **Object** with the same id; nothing merges or splits after lifting.
- **Publication** is the only path from a **Workspace** into the database.

## Flagged ambiguities

- "Run" is never used bare: say **Job**, **Stage Run** or **Compute Run**.
- "Instance" also names a rented provider machine (Vast.ai). In docs, say "rented machine" or "Vast instance" for that, and **Instance** only for the domain term.
