# ---------------------------------------------------------------------------
# Patch for ThingsBoard IoT Gateway KNX connector (knx_connector.py)
#
# Adds support for:
#   * DPT 275.100  -> 4-mode user setpoint (heat/cool/eco...) written as raw
#                     bytes (4 x DPT 9.001 blocks).
#   * DPT 20.102   -> HVAC mode (single byte).
#
# Reason: xknx.tools.group_value_write does not natively encode DPT 275.100,
# so we hand-encode the payload and push raw bytes onto the bus.
#
# Apply with:
#   docker cp tb-gateway:/thingsboard_gateway/connectors/knx/knx_connector.py \
#       ~/knx_connector.py.bak
#   # edit the file inside the container (or copy a patched copy back), then:
#   docker cp ~/knx_connector.py \
#       tb-gateway:/thingsboard_gateway/connectors/knx/knx_connector.py
#   docker restart tb-gateway
# ---------------------------------------------------------------------------

@staticmethod
def __dpt9001_bytes(value):
    encoded = int(round(float(value) * 100.0))
    exponent = 0
    while encoded < -2048 or encoded > 2047:
        encoded = encoded >> 1
        exponent += 1
    mantissa = encoded & 0x7FF
    sign = 1 if float(value) < 0 else 0
    high = (sign << 7) | ((exponent & 0x0F) << 3) | ((mantissa >> 8) & 0x07)
    low = mantissa & 0xFF
    return [high & 0xFF, low & 0xFF]


def __do_group_write(self, group_address, value, data_type):
    if data_type in ('setpoint_heat_user', 'setpoint4', 'setpoint_4_modes'):
        t = float(value)
        payload = (self.__dpt9001_bytes(t) * 4)
        group_value_write(self.__client, group_address, payload)  # raw bytes
    elif data_type in ('hvac_mode', 'hvac_mode_user', 'dpt20102'):
        mode = int(float(value))
        group_value_write(self.__client, group_address, [mode & 0xFF])
    else:
        group_value_write(self.__client, group_address, value, data_type)


# Suggested fix for the uplink converter crash
# (knx_uplink_converter.py ... 'NoneType' object is not subscriptable):
#
#   if hasattr(converted_value, 'value'):
#       converted_value = converted_value.value
