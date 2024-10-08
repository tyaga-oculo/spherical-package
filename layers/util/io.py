import matplotlib.pyplot as plt
import torch
import numpy as np
import array


def torch2numpy(img):
    """
    Converts a torch image to numpy format
    """
    if img.dim() == 4:
        img = img.permute(0, 2, 3, 1).contiguous()
    elif img.dim() == 3:
        img = img.permute(1, 2, 0).contiguous()
    return img.cpu().numpy()


def numpy2torch(img):
    """
    Converts a numpy image to torch format
    """
    img = torch.from_numpy(img)
    if img.dim() == 4:
        img = img.permute(0, 3, 1, 2).contiguous()
    elif img.dim() == 3:
        img = img.permute(2, 0, 1).contiguous()
    return img


def load_numpy_img(path, batch_dim=False):
    """
    Loads an image to numpy format with H x W x C dimensions. If batch_dim==True, then returns a 4D B x H x W x C numpy array.
    """
    from skimage import io
    img = io.imread(path)
    if batch_dim:
        return img[None, ...]
    return img


def load_torch_img(path, batch_dim=False):
    """
    Loads an image to torch format with C x H x W dimensions. If batch_dim==True, then returns a 4D B x C x H x W torch tensor.
    """
    return numpy2torch(load_numpy_img(path, batch_dim))


def read_exr(image_fpath):
    """ Reads an openEXR file into an RGB matrix with floats """
    import OpenEXR, Imath
    f = OpenEXR.InputFile(image_fpath)
    dw = f.header()['dataWindow']
    w, h = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1)
    im = np.empty((h, w, 3))

    # Read in the EXR
    FLOAT = Imath.PixelType(Imath.PixelType.FLOAT)
    channels = f.channels(["R", "G", "B"], FLOAT)
    for i, channel in enumerate(channels):
        im[:, :, i] = np.reshape(array.array('f', channel), (h, w))
    return im


def write_ply(
        output_path,
        pts,  # 3 x N
        normals=None,  # 3 x N
        rgb=None,  # 3 x N
        faces=None,  # 3 x M
        face_rgb=None,  # 3 x M
        text=False):
    import plyfile

    names = 'x,y,z'
    formats = 'f4,f4,f4'
    if normals is not None:
        pts = np.vstack((pts, normals))
        names += ',nx,ny,nz'
        formats += ',f4,f4,f4'
    if rgb is not None:
        pts = np.vstack((pts, rgb))
        names += ',red,green,blue'
        formats += ',u1,u1,u1'
    pts = np.core.records.fromarrays(pts, names=names, formats=formats)
    el = [plyfile.PlyElement.describe(pts, 'vertex')]
    if faces is not None:
        faces = faces.astype(np.int32).T  # Next step needs M x 3 memory layout
        faces = faces.copy().ravel().view([("vertex_indices", "u4", 3)])
        el.append(plyfile.PlyElement.describe(faces, 'face'))
    if face_rgb is not None:
        el.append(plyfile.PlyElement.describe(face_rgb, 'face'))

    plyfile.PlyData(el, text=text).write(output_path)


def write_heatmap(path, data, max_val=None, cmap_type='plasma'):
    '''Writes a heatmap visualization of the data. Data is a NxM np.float32 array'''
    from skimage import io
    assert data.ndim == 2, 'Data must be 2-dimensional'
    assert data.dtype == np.float32, 'Data dtype must be np.float32'

    cmap = plt.get_cmap(cmap_type)
    if max_val is None:
        data = data / data.max()
    else:
        data = data / max_val

    io.imsave(path, cmap(data))


# ----------------------
# Network Training I/O
# ----------------------


def save_checkpoint(state, is_best, filename):
    '''Saves a training checkpoints'''
    torch.save(state, filename)
    if is_best:
        basename = osp.basename(filename)  # File basename
        idx = filename.find(basename)  # Where path ends and basename begins
        # Copy the file to a different filename in the same directory
        shutil.copyfile(filename, osp.join(filename[:idx], 'model_best.pth'))


def load_partial_model(model, loaded_state_dict):
    '''Loaded a save model, even if the model is not a perfect match. This will run even if there is are layers from the current network missing in the saved model.
    However, layers without a perfect match will be ignored.'''
    model_dict = model.state_dict()
    pretrained_dict = {
        k: v
        for k, v in loaded_state_dict.items() if k in model_dict
    }
    model_dict.update(pretrained_dict)
    model.load_state_dict(model_dict)


def load_optimizer(optimizer, loaded_optimizer_dict, device):
    '''Loads the saved state of the optimizer and puts it back on the GPU if necessary.  Similar to loading the partial model, this will load only the optimization parameters that match the current parameterization.'''
    optimizer_dict = optimizer.state_dict()
    pretrained_dict = {
        k: v
        for k, v in loaded_optimizer_dict.items()
        if k in optimizer_dict and k != 'param_groups'
    }
    optimizer_dict.update(pretrained_dict)
    optimizer.load_state_dict(optimizer_dict)
    for state in optimizer.state.values():
        for k, v in state.items():
            if torch.is_tensor(v):
                state[k] = v.to(device)
