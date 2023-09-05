import numpy as np
from PIL import Image
import torch
from torchvision import transforms
import cv2


def dino_predict(dino: torch.nn.Module, pimg: np.ndarray) -> np.ndarray:
    def preprocess_image_array(image_array, target_size):
        # Step 1: Normalize using mean and std of ImageNet dataset
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        image_array = (image_array / 255.0 - mean) / std

        # Step 2: Resize the image_array to the target size
        image_array = np.transpose(image_array, (2, 0, 1))  # PyTorch expects (C, H, W) format
        image_tensor = torch.tensor(image_array, dtype=torch.float32)
        image_tensor = image_tensor.unsqueeze(0)
        image_tensor = resize_image_tensor(image_tensor, target_size=target_size)
        return image_tensor

    def resize_image_tensor(image_tensor, target_size=(224, 224)):
        transform = transforms.Compose([
            transforms.Resize(target_size),
        ])
        resized_image = transform(image_tensor)
        return resized_image

    TARGET_SIZE = (504, 504)
    with torch.no_grad():
        timg = preprocess_image_array(pimg, target_size=TARGET_SIZE)
        print(timg.min(), timg.max(), timg.shape)

        dino.eval()
        outs = dino.forward_features(timg)
        print('output shape:', outs['x_norm_patchtokens'].shape)

        feats = outs['x_norm_patchtokens']
        P = 14
        B, C, H, W = timg.shape
        Ph, Pw = H // P, W // P
        B, PhPw, F = feats.shape
        feats = feats.reshape(B, Ph, Pw, F)
        feats = np.array(feats[0])
    return feats


def sync_feats(feat_list: list[np.ndarray], feat_space: str) -> list[np.ndarray]:
    if feat_space == 'pos':
        for frame_ind in range(len(feat_list)):
            feat_list[frame_ind][:, :, 2] = frame_ind * 10000
    return feat_list

def extract_features(pimg: np.ndarray, feat_space: str, downsampling: dict) -> np.ndarray:
    assert len(pimg.shape) == 3
    if feat_space == 'dino':
        # pimg size should be 504
        dinov2_vits14 = torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')
        feat = dino_predict(dinov2_vits14, pimg)
        assert downsampling['factor'] * feat.shape[0] == pimg.shape[0]
    else:
        pimg = cv2.resize(pimg, dsize=(pimg.shape[0]//downsampling['factor'], pimg.shape[1]//downsampling['factor']))
        if feat_space == 'hue':
            # convert to hsv
            hsv = cv2.cvtColor(pimg, cv2.COLOR_RGB2HSV)
            # extract features
            feat = hsv[..., 0:1]  # hue and value as feature
        elif feat_space == 'rgb':
            feat = pimg  # rgb as feature
        elif feat_space == 'pos':
            # position as features
            feat = np.zeros(pimg.shape[:2] + (3,))
            feat[..., 0] = np.arange(pimg.shape[0])[:, None]  # row
            feat[..., 1] = np.arange(pimg.shape[1])[None, :]  # col
        else:
            raise ValueError(f"Unknown feature extractor: {feat_space}")
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

def compute_probs_soft(dist: np.ndarray, sigma: float = 100) -> np.ndarray:
    """Here we compute the probabilities of being of the same class than the clicks."""
    # dist is B, H, W, C
    # the similarity to a class is exp(-d^2 / 2*sigma^2) 
    # we compute the similarity to all classes and normalize
    sim = np.exp(-dist**2 / (2*sigma**2))
    # sim = 1 / (sigma*dist)  #np.exp(-dist**2 / (2*sigma**2))
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
    # # for research purposes, compute probability of pos and neg as given by your distance function and the softmax
    # pos_class = (probs*click_categories.reshape(1, 1, 1, C)).sum(axis=-1)
    # norm = lambda x : (x - x.min() + 1e-9) / (x.max() - x.min() + 1e-9)
    # for frame_ind in range(B):
    #     with open('pos_class.txt', 'a') as f:
    #         f.write(f'frame ind {frame_ind}\n \
    #                 min {pos_class[frame_ind].min()}\n \
    #                 max {pos_class[frame_ind].max()}')
    #     Image.fromarray(to255(norm(pos_class[frame_ind]))).save(f'pos_class_{frame_ind}.png')
    # neg_class = (probs*(1-click_categories.reshape(1, 1, 1, C))).sum(axis=-1)
    # assert np.allclose(pos_class + neg_class, 1)

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
    imga_up = cv2.resize(imga, (imgb.shape[0], imgb.shape[1]))
    return imga_up

def to255(img):
    assert img.min() >= 0 and img.max() <= 1 and img.min() <= img.max()
    return (img * 255).astype(np.uint8)

def process_img(img: np.ndarray) -> np.ndarray:
    pimg = np.array(Image.fromarray(img).resize((504, 504), resample=Image.Resampling.BILINEAR))
    return pimg

