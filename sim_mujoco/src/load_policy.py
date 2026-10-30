"""Read an rsl_rl policy file (.pt) with numpy only, so PyTorch is not needed.

A .pt file is a zip archive: data.pkl describes the tensors and data/<n> holds their raw
bytes. This rebuilds every tensor as a numpy array and runs the actor network
(Linear layers with ELU activations, the last layer without).
"""

import pickle
import zipfile

import numpy as np

_DTYPES = {"FloatStorage": np.float32, "DoubleStorage": np.float64, "LongStorage": np.int64,
           "IntStorage": np.int32, "HalfStorage": np.float16, "BoolStorage": np.bool_}


def load_checkpoint(path):
    with zipfile.ZipFile(path) as archive:
        prefix = archive.namelist()[0].split("/")[0]

        class Unpickler(pickle.Unpickler):
            def find_class(self, module, name):
                if module == "torch._utils" and name == "_rebuild_tensor_v2":
                    return rebuild_tensor
                if module == "torch" and name.endswith("Storage"):
                    return name
                if module == "collections" and name == "OrderedDict":
                    import collections
                    return collections.OrderedDict
                return lambda *args, **kwargs: None

            def persistent_load(self, pid):
                _, storage_type, key, _location, _size = pid
                raw = archive.read(f"{prefix}/data/{key}")
                return np.frombuffer(raw, dtype=_DTYPES[storage_type])

        def rebuild_tensor(storage, offset, size, stride, *args):
            if not size:
                return storage[offset].copy()
            itemsize = storage.itemsize
            return np.lib.stride_tricks.as_strided(
                storage[offset:], shape=size, strides=[s * itemsize for s in stride]).copy()

        with archive.open(f"{prefix}/data.pkl") as f:
            return Unpickler(f).load()


class Actor:
    """The walking policy: observation vector in, 12 joint actions out."""

    def __init__(self, path):
        weights = load_checkpoint(path)["model_state_dict"]
        names = sorted({k.rsplit(".", 1)[0] for k in weights if k.startswith("actor.")},
                       key=lambda k: int(k.split(".")[1]))
        self.layers = [(weights[f"{n}.weight"], weights[f"{n}.bias"]) for n in names]
        self.obs_dim = self.layers[0][0].shape[1]
        self.act_dim = self.layers[-1][0].shape[0]

    def __call__(self, obs):
        x = np.asarray(obs, dtype=np.float32)
        for i, (w, b) in enumerate(self.layers):
            x = w @ x + b
            if i < len(self.layers) - 1:
                x = np.where(x > 0, x, np.expm1(np.minimum(x, 0)))  # ELU
        return x


if __name__ == "__main__":
    import sys
    ckpt = load_checkpoint(sys.argv[1])
    print("top-level keys:", list(ckpt.keys()))
    for k, v in ckpt["model_state_dict"].items():
        print(f"  {k:<28} {getattr(v, 'shape', v)}")
    actor = Actor(sys.argv[1])
    print("actor input size:", actor.obs_dim, " output size:", actor.act_dim)
    print("output for all-zero input:", np.round(actor(np.zeros(actor.obs_dim)), 3))
