# 03: Deduplicate Objects in segment and lift

**What to build:** Stop one physical thing from becoming several Objects with the same label. Scene
`test1` (f54146f6-4562-4c4f-9ed1-c2b69606b40e) has 172 Objects. 69 same-label pairs overlap by
more than half of the smaller box: 6 "office chair" boxes nest at 1.0, along with 5 "mattress" and
7 "desk". Our hypothesis, not yet verified: `segment.sam3` only drops a mask with IoU > 0.8
against a kept mask
([gpu.py](../../../backend/packages/scene-stages/src/scene_stages/gpu.py) `run`), so a whole-chair
mask and a seat mask with the same label both survive. Lift never merges groups that share a Frame
([lift.py](../../../backend/packages/scene-stages/src/scene_stages/lift.py) `_agglomerate`), so
they stay separate Instances.

Parts stay Objects: door handles, drawers, outlets and switches are wanted for questions such as
"how many outlets are there?". Only same-label duplicates merge. Different-label overlaps such as
"cabinet" and "wardrobe" are out of scope.

**Blocked by:** None

**Status:** ready-for-agent

- [ ] segment: within one Frame, a mask is dropped when most of it (a `containment_threshold`
      param) lies inside a higher-scoring kept mask with the same label.
- [ ] lift: as the Stage's last clustering step, Instances with the same label merge when their
      voxel sets overlap by more than a `merge_overlap` param of the smaller one. Best views and
      label votes recompute for the merged Instance. Nothing merges or splits after lift.
- [ ] Different-label Instances never merge; a door handle inside a wardrobe stays its own Object.
- [ ] Tests on synthetic masks and points: a contained same-label mask is dropped, a contained
      different-label mask is kept, two same-label Instances from different Frames merge, and two
      adjacent same-label chairs do not.
- [ ] Defaults set in `backend/config/pipeline.yaml`; docs/architecture/pipeline.md segment and
      lift rows updated.
- [ ] Live check: reprocess `test1` on the GPU Target. Record in the GPU-INTEGRATION live check log
      the Object count before (172) and after, the same-label overlap pair count before (69) and
      after, and confirm parts remain.
