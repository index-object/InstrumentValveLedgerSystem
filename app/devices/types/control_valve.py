from app.devices.types.valve_base import ValveBase, db


class ControlValve(ValveBase):
    __tablename__ = "control_valves"
