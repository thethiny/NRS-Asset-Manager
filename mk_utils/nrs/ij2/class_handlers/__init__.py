import logging

from mk_utils.nrs.ij2.class_handlers.database import IJ2DatabaseHandler
from mk_utils.nrs.ij2.class_handlers.texture2d import IJ2Texture2DHandler
from mk_utils.nrs.ue3_common import ClassHandler


logging.getLogger("IJ2ClassHandlers").debug("Registering IJ2 handlers")

# Note: IJ2 handlers are registered in a separate handler registry
# to avoid conflicts with MK11 handlers
ij2_handlers = {}

for var in list(locals().values()):
    if isinstance(var, type) and issubclass(var, ClassHandler) and var is not ClassHandler:
        for type_ in var.HANDLED_TYPES:
            ij2_handlers[type_.lower()] = {
                "handler_class": var,
                "args": (),
            }
            logging.getLogger("IJ2ClassHandlers").debug(f"IJ2 type {type_} handled by {var}.")
