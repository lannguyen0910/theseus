from theseus.base.callbacks import CALLBACKS_REGISTRY
from theseus.cv.semantic.callbacks.visualize_callbacks import (
    SemanticVisualizerCallback,
)

CALLBACKS_REGISTRY.register(SemanticVisualizerCallback)
