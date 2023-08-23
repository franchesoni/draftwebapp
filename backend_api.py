import io
from pathlib import Path

from PIL import Image
import numpy as np

from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="draft",
)

class State:
    img = np.random.randint(0, 256, size=(224, 512, 3))

state = State()

@app.get("/hello")
async def helloworld():
    return {"Hello": "World"}

@app.post("/setImg")
async def setImg(file: UploadFile):
    content = await file.read()
    file_obj = io.BytesIO(content)
    pilimg = Image.open(file_obj)
    state.img = np.array(pilimg)
    pilimg.save('curimg.png')
    return {"filename": file.filename}

@app.get("/getImg")
async def getImg():
    state.img = np.random.randint(0, 256, size=(224, 512, 3)).astype(np.uint8)
    pilimg = Image.fromarray(state.img)
    pilimg.save("current_image.jpg")
    return FileResponse("current_image.jpg")


app.mount("/", StaticFiles(directory=".", html=True))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8008)