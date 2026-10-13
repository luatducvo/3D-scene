# 18: Scene Graph — real boxes and Relations

**What to build:** The real CPU Scene Graph Algorithm: gravity-aligned oriented boxes fitted from Instance points, and the seven Relation rules (on, under, above, inside, next_to, near, against_wall) registered through their own entry-point group and selected in configuration. Relations are published and shown in the Object detail panel. Works on fake Instances, so it does not wait for GPU perception.

**Blocked by:** 10

**Status:** done

- [ ] For a fixture layout (e.g. a cup on a table, next to a chair against a wall) the expected Relations are produced and shown in the cup's detail view.
- [ ] Adding a Relation rule needs only a new rule and a config entry.
- [ ] Unit tests cover box fitting, footprint overlap, surface distance and each rule's thresholds.
- [ ] A Stage Algorithm contract test covers the Scene Graph output and Manifest.
