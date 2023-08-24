import io
import logging
logger = logging.getLogger("uvicorn")
import time

from PIL import Image
import numpy as np

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from ourfunctions import extract_features, full_compute_probs, compute_masks, upscale_a_as_b, to255, sync_feats
from state import state, active_websockets, update_viewers, Viewer



downsampling = {'factor':14}
app = FastAPI(
    title="draft",
)

@app.get("/reset")
async def reset():
    state.reset()
    # for key in list(active_websockets.keys()):
    #     del active_websockets[key]
    logger.info('reset!')
    return {"reset": True}

# check that everything works fine
@app.get("/hello")
async def helloworld():
    return {"Hello": "World"}

async def recompute_push_probs_masks():
    # recompute probs
    probs = full_compute_probs(state.feats, state.selected_feats, state.clicks, state.k)
    probs = list(probs)
    # upscale probs
    for ind in range(len(probs)):
        probs[ind] = upscale_a_as_b(probs[ind], state.viewers[ind].pimg)
        state.viewers[ind].prob = to255(probs[ind])  # update viewer
        state.viewers[ind].should_update['prob'] = True
        await update_viewers(active_websockets["viewers"], state.viewers, logger)
    probs = np.array(probs)
    # recompute masks
    masks = compute_masks(probs, state.thresh)
    for ind in range(len(masks)):
        state.viewers[ind].mask = to255(masks[ind]*1)  # update viewer
        state.viewers[ind].should_update['mask'] = True
        await update_viewers(active_websockets["viewers"], state.viewers, logger)

@app.post('/addClick')
async def addClick(data: dict):
    logger.info(f'new click is {data}')
    number_of_clicks = int(data['click'][0])
    try:
        assert number_of_clicks == len(state.clicks) + 1, f"Expected {len(state.clicks) + 1} clicks, got {number_of_clicks}"
    except AssertionError:
        return HTTPException(424, "Missed one previous click")
    frame_ind, col, row, is_pos = data['click'][1]
    state.clicks.append((frame_ind, row, col, is_pos))
    # get features for the new click
    state.selected_feats.append(state.feats[frame_ind][row//downsampling['factor'], col//downsampling['factor']])
    await recompute_push_probs_masks()
    return {"addClick": True}

# @app.post('/setDist')
# async def setDist(data: dict):
#     logger.info(f'new distance is {data}')
#     state.dist = data['dist']
#     # recompute distances
#     # recompute probs
#     # recompute masks
#     # update viewers
#     return {"setDist": True}

@app.post('/setFeatSpace')
async def setDist(data: dict):
    logger.info(f'new feature space is {data}')
    state.feat_space = data['featSpace']
    for ind in range(len(state.viewers)):
        # update feats
        state.feats[ind] = extract_features(state.viewers[ind].pimg, state.feat_space, downsampling)
    state.feats = sync_feats(state.feats, state.feat_space)
    for click_ind, click in enumerate(state.clicks):
        frame_ind, row, col, cat = click
        state.selected_feats[click_ind] = state.feats[frame_ind][row//downsampling['factor'], col//downsampling['factor']]
    await recompute_push_probs_masks()
    return {"setFeatSpace": True}

@app.post("/setK")
async def setK(data: dict):
    logger.info(f'new k is {data}')
    state.k = int(data["k"])
    await recompute_push_probs_masks()
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
    if 'viewers' not in active_websockets:
        raise HTTPException(status_code=424, detail="Websocket not connected")
    # receive image
    content = await file.read()
    file_obj = io.BytesIO(content)
    pilimg = Image.open(file_obj)
    # create new viewer
    new_viewer = Viewer(np.array(pilimg))
    state.viewers.append(new_viewer)
    await update_viewers(active_websockets["viewers"], state.viewers, logger)  # push new processed image to frontend
    # compute features for the new image
    state.feats.append(extract_features(new_viewer.pimg, state.feat_space, downsampling))
    state.feats = sync_feats(state.feats, state.feat_space)
    # compute probs for the new image
    new_img_probs = full_compute_probs(state.feats[-1:], state.selected_feats, state.clicks, state.k)
    assert new_img_probs.shape[0] == 1, f"Expected 1 image, got {new_img_probs.shape[0]}"
    # upscale probs
    new_img_probs = upscale_a_as_b(new_img_probs[0], new_viewer.pimg)
    new_viewer.prob = to255(new_img_probs)  # update viewer
    new_viewer.should_update['prob'] = True
    assert 'viewers' in active_websockets, "Websocket not connected"
    await update_viewers(active_websockets["viewers"], state.viewers, logger)
    # compute mask for the new image
    new_img_mask = compute_masks(new_img_probs, state.thresh)
    new_viewer.mask = to255(new_img_mask*1)  # update viewer
    new_viewer.should_update['mask'] = True
    assert 'viewers' in active_websockets, "Websocket not connected"
    await update_viewers(active_websockets["viewers"], state.viewers, logger)

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
        logger.info(f'active ws: {active_websockets}')
        if 'viewers' in active_websockets:
            del active_websockets['viewers']




app.mount("/", StaticFiles(directory=".", html=True))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)