# Domain glossary

| Term | Meaning |
|---|---|
| Scene | One captured room and the understanding derived from its capture. |
| Frame | One image from a photo capture or a moment in a video. |
| Keyframe | A Frame selected as useful for understanding the Scene. |
| Stage | One named transformation in the Scene processing sequence. |
| Algorithm | A chosen method for performing a Stage. |
| Target | A place where an Algorithm executes. |
| Workspace | The working inputs and derived artifacts belonging to one Scene. |
| Manifest | A summary describing the artifacts and outcome produced by a Stage. |
| Vocabulary | The set of concepts available for naming detected things. |
| Job | One request to process a Scene through its Stages. |
| Stage Run | The record of a completed Stage, identifying its Algorithm and settings. |
| Compute Run | One execution of an Algorithm on a compute Target. |
| Instance | A thing distinguished from other things across captured views, with a stable identity. |
| Object | An Instance enriched with its spatial extent, labels and attributes; its identity is unchanged. |
| Relation | A spatial connection between Objects, or between an Object and the room. |
| Scene Graph | The Objects and Relations describing a Scene. |

Use Job, Stage Run or Compute Run explicitly; bare “Run” is ambiguous. Each Instance becomes exactly
one Object with the same identity, with no later merging or splitting.
