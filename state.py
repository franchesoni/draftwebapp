from typing import Literal
import numpy as np
from PIL import Image
import io

# now create a type distance that can be either "euclidean" or "cosine" but nothing more
Distance = Literal["euclidean", "cosine"]
# new type click which is a tuple of three ints and a bool
SClick = tuple[int, int, int, bool]  # stacked click: frame, row, col, category

# next line defines a new viewer object that is a dict of img, mask, prob
class Viewer:
    def __init__(self, img: np.ndarray):
        self.orig_img = img
        self.pimg = self.process_img(self.orig_img)  # int8, also in frontend
        self.mask: np.ndarray  # bool, also in frontend
        self.prob: np.ndarray  # float, also in frontend
        self.should_update = {'pimg': True, 'mask': False, 'prob': False}

    @staticmethod
    def process_img(img: np.ndarray):
        pimg = np.array(Image.fromarray(img).resize((512, 512), resample=Image.Resampling.BILINEAR))
        return pimg




class State:
    viewers: list[Viewer] = []  # everything visible
    clicks: list[SClick] = []
    feats: list[np.ndarray] = []
    selected_feats: list[np.ndarray] = []  # one feature per click
    k: int = 1  # k-nn's k
    thresh: float = 0.5  # prob threshold over probs
    dist: Distance = "euclidean"  # distance metric
    feat_space: str = "pos"  # feature space
    
    def reset(self):
        self.viewers = []
        self.clicks = []
        self.feats = []
        self.selected_feats = []
        self.k = 1
        self.thresh = 0.5
        self.dist = "euclidean"


state, active_websockets = State(), {}
def describe(array: np.ndarray):
    return f"shape: {array.shape}, dtype: {array.dtype}, min: {array.min()}, max: {array.max()}"

async def update_viewers(ws, viewers, logger):
    for vind, viewer in enumerate(viewers):
        if viewer.should_update['pimg']:
            logger.info(describe(viewer.pimg))
            buffer = io.BytesIO()
            Image.fromarray(viewer.pimg).convert("RGB").save(buffer, format="JPEG")
            await ws.send_text(f"{vind},pimg")
            await ws.send_bytes(buffer.getvalue())
            viewer.should_update['pimg'] = False
        if viewer.should_update['mask']:
            logger.info(describe(viewer.mask))
            buffer = io.BytesIO()
            Image.fromarray(viewer.mask).save(buffer, format="PNG")
            await ws.send_text(f"{vind},mask")
            await ws.send_bytes(buffer.getvalue())
            viewer.should_update['mask'] = False
        if viewer.should_update['prob']:
            logger.info(describe(viewer.prob))
            buffer = io.BytesIO()
            Image.fromarray(viewer.prob).save(buffer, format="PNG")
            await ws.send_text(f"{vind},prob")
            await ws.send_bytes(buffer.getvalue())
            viewer.should_update['prob'] = False