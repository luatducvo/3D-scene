from pathlib import Path
from pydantic import BaseModel
STAGES=("ingest","recon","align","mesh","segment","lift","embed","attributes","graph")
OUTPUTS={"ingest":["keyframes"],"recon":["recon"],"align":["align"],"mesh":["mesh"],"segment":["segment"],"lift":["instances"],"embed":["embeddings"],"attributes":["attributes"],"graph":["graph"]}
class SceneWorkspace:
    def __init__(self,data_dir: Path,scene_id: str):
        if not scene_id or any(x in scene_id for x in ("/","\\","..",":")):
            raise ValueError("Invalid scene id")
        self.scene_id=scene_id
        self.root=(Path(data_dir)/"scenes"/scene_id).resolve()
    def path(self,*parts: str)->Path:
        candidate=self.root.joinpath(*parts).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Path outside workspace")
        return candidate
    def dir(self,*parts: str)->Path:
        result=self.path(*parts);result.mkdir(parents=True,exist_ok=True);return result
class IngestManifest(BaseModel):
    num_inputs:int
    num_keyframes:int
    rejected:dict[str,list[str]]
class ReconManifest(BaseModel):
    num_frames:int
    frame_ids:list[str]
    metric_scale:float
    image_size:tuple[int,int]
class AlignManifest(BaseModel):
    world_to_aligned:list[list[float]]
    floor_z:float
    ceiling_height:float|None=None
class MeshManifest(BaseModel):
    mesh_file:str
    points_file:str
    num_faces:int
    num_points:int=0
class SegmentManifest(BaseModel):
    num_masks:int
    vocabulary_size:int
class LiftManifest(BaseModel):
    num_instances:int
    instances_file:str
class EmbedManifest(BaseModel):
    model_id:str
    dim:int
    embeddings_file:str
class AttributesManifest(BaseModel):
    num_objects:int
    invalid_outputs:int=0
class GraphManifest(BaseModel):
    num_objects:int
    num_relations:int
