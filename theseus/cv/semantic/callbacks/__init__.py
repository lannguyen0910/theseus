from theseus.base.callbacks import CALLBACKS_REGISTRY
from theseus.cv.semantic.callbacks.visualize_callbacks import (
    SemanticVisualizerCallbacks,
)

CALLBACKS_REGISTRY.register(SemanticVisualizerCallbacks)