# Unify how the Scene viewer displays Objects

Status: ready-for-agent

## Problem Statement

The Scene viewer already offers every display a user needs to explore a room: the point cloud or the mesh, Instance Colors, the Object Heatmap of a Search, a hover tint and a Selection. They grew one at a time, so they do not form one coherent display:

- The point cloud and the mesh can be switched in two places. The topbar buttons show exactly one of them, but the "Display layers" panel has two independent switches that can show both at once or neither.
- Instance Colors is a pair of `original | instances` buttons next to an unrelated "Clear" button that does what the Search box's own clear already does.
- Hovering an Object only lightens it towards white, which says little about which points belong to it.
- Clicking an Object paints it orange, flies the camera to it and opens the Object Details panel, even when the user only wanted to see what it is.
- Search, hover and Selection all paint at once and stack on each other, so a Search's Object Heatmap gets covered by hover and Selection tints and the user cannot tell which display is speaking.

## Solution

The viewer shows the room in one of two geometry modes and paints Objects in one of three mutually exclusive interaction states.

- **Geometry mode**: one two-way switch, Points or Mesh, always showing exactly one. It defaults to Points when the Scene has a point cloud, else Mesh. The point-size slider sits beside the switch and appears only in Points mode. The "Display layers" panel and the topbar "Clear" button disappear.
- **Instance Colors**: one on/off switch, independent of the geometry mode, that paints each Object in its own stable colour. It only colours; it adds no boxes or labels. It is disabled when Object Membership is missing or does not fit the shown geometry, and the existing "Object highlighting could not be loaded." notice stays.
- **Three interaction states**, exactly one at a time:
  - **Idle**: hovering an Object paints it in its own Instance Color and shows its label next to the cursor. With Instance Colors on, every other Object dims instead. Clicking an Object selects it.
  - **Search** (while the Search box holds text): the Search Hits are painted as an Object Heatmap, everything else is dimmed, the legend shows and the camera flies to the hits, as today. Hover is off. Only a Search Hit can be clicked; clicking it selects it, empties the Search box and drops the Highlight. Clicking empty space or an Object that is not a hit does nothing. Esc, or clearing the Search box, returns to Idle.
  - **Selection**: the selected Object is painted the way hover paints in Idle and keeps a persistent label with its name anchored above its box in 3D. Hover is off. Clicking another Object selects it instead. Clicking empty space or Esc returns to Idle; a previous Search does not come back. Typing a Search drops the Selection and closes Object Details. The camera does not move on Selection.
- **Object Details** opens only from a new button among the spatial tools. The button is always visible and disabled without a Selection. Dropping the Selection closes the panel, and selecting another Object while it is open shows that Object.

## User Stories

1. As a user, I want one Points/Mesh switch, so that I always know which geometry I am looking at.
2. As a user, I want the viewer never to show the point cloud and the mesh at once or neither of them, so that the room never looks doubled or empty.
3. As a user, I want the viewer to open on the point cloud when the Scene has one and on the mesh otherwise, so that I see the richest geometry first.
4. As a user, I want the Points option disabled when the Scene has no point cloud, and the Mesh option disabled when it has no mesh, so that I cannot pick a mode with nothing to show.
5. As a user, I want the point-size slider beside the geometry switch and only in Points mode, so that it appears where and when it matters.
6. As a user, I want no "Display layers" panel or button, so that there is one place to change the geometry.
7. As a user, I want one Instance Colors switch, so that I can see every Object the Scene recognised in its own colour.
8. As a user, I want Instance Colors to work in both Points and Mesh mode, so that switching geometry keeps my choice.
9. As a user, I want each Object to keep the same colour every time I turn Instance Colors on, so that I can recognise Objects across visits.
10. As a user, I want similar-looking Object ids to get clearly different colours, so that neighbouring Objects do not blend together.
11. As a user, I want points and vertices that belong to no Object to keep their captured colour under Instance Colors, so that I can tell recognised from unrecognised geometry.
12. As a user, I want a point shared by several Objects to take the colour of the smallest one, so that a handle stands out from the wardrobe around it.
13. As a user, I want the Instance Colors switch disabled, with the existing notice, when Object Membership is missing or does not fit the geometry, so that I am not offered a switch that does nothing.
14. As a user, I want hovering an Object to paint it in its own Instance Color, so that I see exactly which points belong to it.
15. As a user, I want the hovered Object's label next to the cursor, so that I know what it is without clicking.
16. As a user, I want hovering under Instance Colors to dim every other Object, so that the hovered one stands out among the colours.
17. As a user, I want hover to stop the moment I leave the Object or the canvas, so that no paint is left behind.
18. As a user, I want no hover while measuring or dragging the camera, so that Measurement and navigation are not disturbed.
19. As a user, I want clicking an Object to select it without moving the camera, so that I keep my point of view.
20. As a user, I want the selected Object painted the way hover paints it, so that hover and Selection speak the same visual language.
21. As a user, I want the selected Object's name shown above it in 3D, following the camera, so that I keep seeing what I selected.
22. As a user, I want hover switched off while an Object is selected, so that only the Selection is painted.
23. As a user, I want clicking another Object while one is selected to select that one directly, so that I can compare Objects quickly.
24. As a user, I want clicking empty space or pressing Esc to drop the Selection and bring hover back, so that I can return to browsing.
25. As a user, I want the Object Details panel not to open on its own, so that a click only shows me the Object.
26. As a user, I want an Object Details button among the spatial tools, so that I open the details only when I ask for them.
27. As a user, I want that button disabled when nothing is selected, so that I know details belong to a Selection.
28. As a user, I want the open Object Details panel to follow my Selection and to close when I drop it, so that it never shows a stale Object.
29. As a user, I want a Search to keep painting its hits as an Object Heatmap with the rest dimmed, so that I see how well each hit matches relative to the others.
30. As a user, I want the heatmap legend while a Search shows hits, so that I can read the colours.
31. As a user, I want the camera to fly to the Search Hits, so that I find them in the room.
32. As a user, I want Search Hits under Instance Colors to keep the heatmap and the rest to stay in dimmed Instance Colors, so that switching appearance does not hide the Search.
33. As a user, I want hover switched off during a Search, so that nothing covers the heatmap.
34. As a user, I want the cursor to show a pointer only over Objects I can click in the current state, so that I know what a click will do.
35. As a user, I want clicking a Search Hit to select it, empty the Search box and drop the heatmap, so that I move from finding to inspecting.
36. As a user, I want clicking empty space or a non-hit Object during a Search to do nothing, so that a stray click does not lose my results.
37. As a user, I want Esc or the Search box's clear to end the Search and bring hover back, so that I can return to browsing.
38. As a user, I want a previous Search not to return when I drop a Selection, so that each state starts clean.
39. As a user, I want typing a Search while an Object is selected to drop the Selection and close Object Details, so that Search takes over cleanly.
40. As a user, I want a slow Search not to overwrite a newer one or a Selection I made meanwhile, so that what I see matches what I did last.
41. As a user, I want no separate "Clear" button in the topbar, so that the Search box is the one place to clear a Search.
42. As a user, I want Reset view, Measurement and Scene info to work as before, so that the unification changes nothing else.

## Implementation Decisions

- Scope is the Scene viewer page only: the explorer component, the viewer canvas and its layers, the viewer store and the pure viewer modules. Upload and Job progress screens are untouched.
- **Viewer store owns the interaction state.**
  - It gains the Search text, so that selecting a Search Hit can empty the Search box from outside the explorer component. The explorer's input reads and writes it; the debounced Search request still starts from the explorer.
  - The interaction state is derived, never stored separately: Selection when an Object is selected, else Search when the Search text is non-blank, else Idle. Search counts as active while the text is non-blank, whether the request is in flight, failed or returned no hits.
  - Store actions replace the canvas's direct `select`/`deselect` calls with intent-level ones, roughly: a hover action that is ignored outside Idle; a click action taking the clicked Object id or none, applying the per-state rules in the Solution; an escape action (drop Selection, else end Search, and stop Measurement as today); setting the Search text, which drops any Selection.
  - A pure "can this Object be clicked now" rule (any Object in Idle and Selection, only Search Hits in Search) drives both the click action and the pointer cursor.
  - Selecting an Object drops the Search: it empties the Search text, clears the Highlight and similarities, and advances the result version so an in-flight Search response is discarded.
  - The panel being open stays component state; opening Object Details no longer follows the Selection automatically, but dropping the Selection still closes it.
- **Camera**: a Selection no longer calls `focus`. Search still focuses its hits. Reset view only moves the camera, as the code already does.
- **Painter** (`highlight.ts`) paints one interaction state at a time instead of stacking highlight, selection and hover:
  - It always knows every Object's Instance Color, whatever the appearance, because hover and Selection paint with it in original appearance too.
  - Idle with no hover: the appearance as is.
  - Emphasised Object (hovered in Idle, or selected): its owned elements in its Instance Color; under Instance Colors the other elements dimmed by the existing `DIM` factor, in original appearance the others unchanged.
  - Search: hits in heatmap colours, everything else dimmed in the current appearance.
  - Ownership for every paint stays the smallest-Object rule shared with picking.
  - The white hover tint (`HOVER_MIX`), the orange Selection colour and the plain green Highlight colour (`HIGHLIGHT_COLOR`, reached only by a Highlight without similarities) are removed; a Highlight always comes from a Search with similarities.
- **Geometry mode**: `view.ts` keeps `ViewMode` as exactly one of points or mesh. The per-layer toggle action in the store and the panel switches go; the store sets layers only through the mode.
- **Labels**: the hover label keeps its cursor-following tooltip. A new persistent Selection label is rendered in the canvas, anchored at the top centre of the selected Object's box, showing the Object's label.
- **Strings**: the `layers` panel strings, `layersSubtitle`, `displayLayers`, `appearance.clear` and the `original | instances` pair give way to an Instance Colors switch label and an Object Details button label, all in `messages/en.json`.
- **Glossary**: the relationship "Selecting an Object keeps the current Highlight" becomes "Selecting an Object ends the Search and clears its Highlight; a new Search clears the Selection". The Highlight and Selection definitions otherwise stand. The architecture page for the frontend drops the `layers` panel from its list of side panels.
- No backend, API contract, file format or Publication change.

## Testing Decisions

- A good test drives the viewer the way a user does and asserts what the user would see: which state the viewer is in, what the Search box holds, which Object is selected, which panel is open, and the colour of each point. It does not assert private fields, effect order or markup structure.
- **Viewer store** (new tests beside the store): walk the three states through the intent actions: hover is ignored in Search and Selection; clicking a hit during Search selects it and empties the Search text; clicking a non-hit or nothing during Search changes nothing; clicking another Object in Selection switches; Esc drops Selection, else ends Search; typing a Search drops the Selection; a stale Search response after a Selection is discarded; the clickable rule matches the cursor rule.
- **Painter** (extend `highlight.test.ts`): per-point colours for hover and Selection in both appearances (Instance Color on the emphasised Object, others unchanged or dimmed), the heatmap under both appearances, Instance Colors stable and distinguishable, shared points owned by the smallest Object, and a return to plain appearance when the emphasis ends.
- **View rules** (extend `view.test.ts`): the default mode and that switching shows exactly one layer; Instance Colors availability follows the existing highlight-availability rule.
- **Explorer component**: interactive tests that render the explorer against the mock API (MSW handlers, as `SceneExplorer.test.tsx` does), with the WebGL canvas replaced by a stub and canvas clicks and hovers driven through the store's intent actions. They cover: one Points/Mesh switch and no Display layers panel; the point-size slider only in Points mode; the Instance Colors switch and its disabled state without membership; the Object Details button disabled without a Selection, opening the panel only on press, following the Selection and closing on deselect; selecting a Search Hit emptying the Search box; no topbar Clear button. This needs a DOM test environment (jsdom with React Testing Library) as new dev dependencies, scoped to these component tests; existing static-markup tests stay as they are.
- Prior art: `highlight.test.ts` for per-point colour assertions on synthetic membership, `view.test.ts` for pure view rules, `SceneExplorer.test.tsx` for the mock API through `setupServer(...handlers)` and resetting the store between tests.
- Done check: `npm run typecheck`, `npm test` and `npm run build` in `frontend/`.

## Out of Scope

- Pages other than the Scene viewer.
- Boxes or labels for every Object under Instance Colors.
- A list of Search Hits to click from, or any change to how Search ranks Objects or normalises the Object Heatmap.
- Measurement, Reset view and Scene info behaviour.
- Combining Search with Selection or hover; the three states stay exclusive by design.
- Backend, Pipeline, Publication and API changes.

## Further Notes

- The decisions come from a grilling session on 2026-10-23. The user first accepted stacked states (hover and Selection painted together, hover over the heatmap, Selection keeping the Highlight), then replaced them with the exclusive Idle / Search / Selection model above.
- Domain terms follow `GLOSSARY.md`: Instance Colors (not "segmentation view"), Object Membership, Search, Search Hit, Object Heatmap, Highlight, Selection.
