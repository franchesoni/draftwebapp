import numpy as np
import cv2

def extract_features(pimg: np.ndarray) -> np.ndarray:
    feat_ext = 'hv'
    if feat_ext == 'hv':
        # convert to hsv
        hsv = cv2.cvtColor(pimg, cv2.COLOR_RGB2HSV)
        # extract features
        feat = hsv[..., [True, False, True]]  # hue and value as feature
    else:
        raise ValueError(f"Unknown feature extractor: {feat_ext}")
    return feat

def compute_distances(feat: list[np.ndarray], selected_feat: list[np.ndarray]) -> np.ndarray:
    check_feat_sfeat(feat, selected_feat)
    feats = np.array(feat)[:, :, :, None, :]  # B, H, W, 1, F
    sfeats = np.array(selected_feat)[None, None, None, :, :]  # 1, 1, 1, C, F
    dist = np.linalg.norm(feats - sfeats, axis=-1)  # B, H, W, C
    return dist

def check_feat_sfeat(feat: list[np.ndarray], selected_feat: list[np.ndarray]):
    assert len(feat[0].shape) == 3, f"Expected 3D array, got {feat[0].shape}"
    assert len(selected_feat[0].shape) == 1, f"Expected 1D array, got {selected_feat[0].shape}"
    assert feat[0].shape[-1] == selected_feat[0].shape[0], f"Expected last dimension of feat to be {selected_feat[0].shape[0]}, got {feat[0].shape[-1]}"
    # check that all features have the same shape, we use this to put everything on a tensor
    for f in feat:
        assert f.shape == feat[0].shape, f"Expected all features to have shape {feat[0].shape}, got {f.shape}"
    for sf in selected_feat:
        assert sf.shape == selected_feat[0].shape, f"Expected all selected features to have shape {selected_feat[0].shape}, got {sf.shape}"

def compute_probs_soft(dist: np.ndarray) -> np.ndarray:
    """Here we compute the probabilities of being of the same class than the clicks."""
    # dist is B, H, W, C
    # the similarity to a class is exp(-d^2 / 2*sigma^2) where sigma=1
    # we compute the similarity to all classes and normalize
    sim = np.exp(-dist**2 / 2)
    # the probabilities are a softmax over the classes
    expsim = np.exp(sim)
    probs = expsim / np.sum(expsim, axis=-1, keepdims=True)
    return probs

def compute_probs_knn(probs, clicks, K):
    """Compute probs as average vote of the K nearest neighbors."""
    # probs is B, H, W, C
    # click categories is C
    click_categories = np.array([c[3] for c in clicks])  # frame, row, col, cat -> C
    # we compute the k nearest neighbors
    # we first flatten the probs
    B, H, W, C = probs.shape
    probs_flat = probs.reshape(-1, probs.shape[-1])  # B*H*W, C
    # get the top k indices for each pixel
    topk = np.argpartition(probs_flat, -K, axis=-1)[:, -K:]  # B*H*W, K
    # get categories instead of probs
    topk_cats = click_categories[topk]  # B*H*W, K
    # categories can be either 1 or 0, therefore take an average. Thresholding at 0.5 will get the majority class when K is odd
    probs = np.mean(topk_cats, axis=-1)  # B*H*W
    # reshape probs
    probs = probs.reshape(B, H, W)  # B, H, W
    assert probs.min() >= 0 and probs.max() <= 1
    return probs

def full_compute_probs(feat, selected_feat, clicks, K):
    """Compute the probabilities of being of the same class than the clicks."""
    if len(clicks) == 0:
        return np.zeros(np.array(feat).shape[:3])  # B, H, W
    dist = compute_distances(feat, selected_feat)
    probs = compute_probs_soft(dist)
    probs = compute_probs_knn(probs, clicks, K)
    return probs

def compute_masks(probs: np.ndarray, thresh: float) -> np.ndarray:
    """Here we compute the masks from the probabilities."""
    # probs is B, H, W
    # we threshold the probs
    mask = probs > thresh
    return mask

def upscale_a_as_b(imga, imgb):
    """Upscale imga to the size of imgb."""
    # imga is H, W, C
    # imgb is H', W', C
    # we want to upscale imga to the size of imgb
    # we first compute the ratio of sizes
    ratioy = imgb.shape[0] / imga.shape[0]
    ratiox = imgb.shape[1] / imga.shape[1]
    imga_up = cv2.resize(imga, (0, 0), fx=ratiox, fy=ratioy)
    return imga_up

def to255(img):
    assert img.min() >= 0 and img.max() <= 1 and img.min() <= img.max()
    return (img * 255).astype(np.uint8)
