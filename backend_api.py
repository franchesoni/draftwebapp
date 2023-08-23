import io
import logging
logger = logging.getLogger("uvicorn")
from typing import Literal

from PIL import Image
import cv2
import numpy as np

from fastapi import FastAPI, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from ourfunctions import extract_features, full_compute_probs, compute_masks, upscale_a_as_b, to255

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



# now create a type distance that can be either "euclidean" or "cosine" but nothing more
Distance = Literal["euclidean", "cosine"]
# new type click which is a tuple of three ints and a bool
SClick = tuple[int, int, int, bool]  # stacked click: frame, row, col, category

class State:
    viewers: list[Viewer] = []  # everything visible
    clicks: list[SClick] = []
    feats: list[np.ndarray] = []
    selected_feats: list[np.ndarray] = []  # one feature per click
    k: int = 1  # k-nn's k
    thresh: float = 0.5  # prob threshold over probs
    dist: Distance = "cosine"  # distance metric

async def update_viewers(ws, viewers):
    for vind, viewer in enumerate(viewers):
        if viewer.should_update['pimg']:
            buffer = io.BytesIO()
            Image.fromarray(viewer.pimg).convert("RGB").save(buffer, format="JPEG")
            await ws.send_text(f"{vind},pimg")
            await ws.send_bytes(buffer.getvalue())
            viewer.should_update['pimg'] = False
        if viewer.should_update['mask']:
            buffer = io.BytesIO()
            Image.fromarray(viewer.mask).save(buffer, format="PNG")
            await ws.send_text(f"{vind},mask")
            await ws.send_bytes(buffer.getvalue())
            viewer.should_update['mask'] = False
        if viewer.should_update['prob']:
            buffer = io.BytesIO()
            Image.fromarray(viewer.prob).save(buffer, format="PNG")
            await ws.send_text(f"{vind},prob")
            await ws.send_bytes(buffer.getvalue())
            viewer.should_update['prob'] = False


app = FastAPI(
    title="draft",
)
state, active_websockets = State(), {}

@app.get("/reset")
async def reset():
    global state, active_websockets
    state, active_websockets = State(), {}
    logger.info('reset!')
    return {"reset": True}

# check that everything works fine
@app.get("/hello")
async def helloworld():
    return {"Hello": "World"}

@app.post('/setDist')
async def setDist(data: dict):
    logger.info(f'new distance is {data}')
    state.dist = data['dist']
    # recompute distances
    # recompute probs
    # recompute masks
    # update viewers
    return {"setDist": True}

@app.post("/setK")
async def setK(data: dict):
    logger.info(f'new k is {data}')
    state.k = int(data["k"])
    # recompute probs
    # recompute masks
    # update viewers
    return {"setK": True}

@app.post("/setThresh")
async def setThreshold(data: dict):
    logger.info(f'new threshold is {data}')
    state.thresh = float(data["thresh"])
    # recompute masks
    # update viewers
    return {"setThresh": True}

@app.post("/newImg")
async def setImg(file: UploadFile):
    """This function creates a new viewer and adds a new image to it. It then launches"""
    # receive image
    content = await file.read()
    file_obj = io.BytesIO(content)
    pilimg = Image.open(file_obj)
    # create new viewer
    new_viewer = Viewer(np.array(pilimg))
    state.viewers.append(new_viewer)
    await update_viewers(active_websockets["viewers"], state.viewers)  # push new processed image to frontend
    # compute features for the new image
    state.feats.append(extract_features(new_viewer.pimg))
    # compute probs for the new image
    new_img_probs = full_compute_probs(state.feats[-1:], state.selected_feats, state.clicks, state.k)
    assert new_img_probs.shape[0] == 1, f"Expected 1 image, got {new_img_probs.shape[0]}"
    # upscale probs
    new_img_probs = upscale_a_as_b(new_img_probs[0], new_viewer.pimg)
    # compute mask for the new image
    new_img_mask = compute_masks(new_img_probs, state.thresh)
    # update the viewer
    new_viewer.prob = to255(new_img_probs)
    new_viewer.mask = new_img_mask
    new_viewer.should_update['mask'] = True
    new_viewer.should_update['prob'] = True
    # update viewers
    assert 'viewers' in active_websockets, "Websocket not connected"
    await update_viewers(active_websockets["viewers"], state.viewers)
    logger.info(f'n viewers {len(state.viewers)}')
    return {"newImg": True}

# when a new click comes, we 1. add it to the list of clicks, 2. get the selected feature, 3. compute the distances for the new click, 4. update the probs, 5. update the masks, 6. update the viewers

# websocket endpoints
@app.websocket("/ws/viewers")
async def viewers_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets['viewers'] = websocket
    logger.info('viewers websocket connected')
    try:
        while True:
            received_text = await websocket.receive_text()
            logger.info(received_text)
    except WebSocketDisconnect:
        logger.info('viewers websocket disconnected')
        del active_websockets["viewers"]



app.mount("/", StaticFiles(directory=".", html=True))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8008)