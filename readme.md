barebones webapp that allows to load images from the frontend to the backend and from the backend to the frontend using Python FastAPI at the backend and js+html at the frontend

the idea of this app is the following:
- let most things be handled by the backend
- let the user upload images to the backend
- reset when refresh
- make the backend handle images, clicks, predictions and masks
- update only necessary things
- make the frontend show those things

implementation:
- the frontend makes requests and the backend returns a new state which is a list of viewers and a list of update flags. When the update flag is False the frontend should ignore the viewer.

- buttons and sliders:
- k for knn (slider):
- metric to choose euclidean / cosine (radial button)
- threshold (slider):

issues:
- mask and probs aren't set correctly