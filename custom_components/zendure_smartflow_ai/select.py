from __future__ import annotations
from homeassistant.components.select import SelectEntity
from .const import *

class ZendureOperationMode(SelectEntity):
    _attr_name = "Betriebsmodus"
    _attr_options = MODES
    _attr_current_option = MODE_AUTOMATIC
