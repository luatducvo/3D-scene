# Object Descriptions replace image embeddings, and embed runs after objects

An Object's embedding used to be a MetaCLIP 2 image embedding of its Best View crops, searched cross-modally with MetaCLIP's text tower. We replaced that with the MG3D-Doc method, `embed.mg3d_doc`. A VLM (Qwen3-VL) writes a three-sentence English Object Description covering appearance, use and physical placement, and a multilingual sentence model (bge-m3, 1024 dimensions) embeds that text. At Search time a cross-encoder (bge-reranker-v2-m3) re-judges the top-K hits against their Descriptions. We made this change because CLIP-style text encoders cut input off at 77 tokens and match short alt-text well but spatial, compositional queries poorly ("the lamp on the desk"). Text-to-text retrieval handles those queries and Vietnamese ones.

## Consequences

- The placement sentence needs every Object's final box, so the Pipeline order became `… lift, objects, embed`; embed now reads the objects Stage's output.
- Visual detail reaches Search only through what the VLM puts into words; there is no image vector left to fall back on.
- Object Descriptions are published and stored per Object because the reranker reads them at Search time; they are not exposed to the frontend.
- Search returns only the reranked top-K, and a Search Hit's score is the reranker's relevance plus the label bonus, not cosine similarity.

## Considered Options

- Embedding the Descriptions with MetaCLIP 2's text tower: it adds no weights and keeps an image-compatible space, but the 77-token limit cuts off the placement sentence.
- Keeping MetaCLIP image vectors alongside the text vectors and fusing their scores: rejected for the second vector column, the second query model and the fusion weights it would need.
- Computing placement from Instance points inside embed so the Stage order stays the same: rejected in favour of using the objects Stage's boxes, so the Description cannot disagree with the box the viewer shows.
