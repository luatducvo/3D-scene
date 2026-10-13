# 09: Reprocess from a Stage and skip unchanged Stages

**What to build:** Reprocessing a `ready` or `failed` Scene skips Stages whose Stage Run has the same config hash and whose outputs still exist, and forces every Stage after the first one that runs. Process accepts an optional starting Stage; the Scene page offers a "rerun from Stage" control.

**Blocked by:** 07

**Status:** done

- [ ] Reprocessing with unchanged config reports every Stage as skipped and ends `ready`.
- [ ] Reprocessing from a chosen Stage reruns it and every later Stage; earlier ones are skipped.
- [ ] Changing one Stage's params reruns that Stage and all later ones.
- [ ] Deleting a Stage's output folder makes that Stage rerun even with a matching Stage Run.
- [ ] Skipped Stages show as skipped in the StageStepper.
- [ ] API tests cover each rule above.
