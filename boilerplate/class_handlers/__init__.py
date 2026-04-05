"""
Handler registration for this game.

Import all handler classes here. The registration loop at the bottom
auto-discovers ClassHandler subclasses and builds the handler registry.

To add a new handler:
1. Copy handler_template.py and implement parse()/save()
2. Import the class here
3. The loop below auto-registers it by HANDLED_TYPES
"""

import logging

from mk_utils.nrs.GAME.class_handlers.serializable import GameSerializableHandler  # TODO: rename GAME
# TODO: Import additional handlers here
# from mk_utils.nrs.GAME.class_handlers.texture2d import GameTexture2DHandler
from mk_utils.nrs.ue3_common import ClassHandler


logging.getLogger("ClassHandlers").debug("Registering handlers")

GAME_handlers = {}  # TODO: rename to match game code (e.g., ij2_handlers, mk11_handlers)

for var in list(locals().values()):
    if isinstance(var, type) and issubclass(var, ClassHandler) and var is not ClassHandler:
        for type_ in var.HANDLED_TYPES:
            GAME_handlers[type_.lower()] = {
                "handler_class": var,
                "args": (),
            }
            logging.getLogger("ClassHandlers").debug(f"Type {type_} handled by {var}.")
