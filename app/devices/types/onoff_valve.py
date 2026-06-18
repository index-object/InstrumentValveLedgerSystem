from app.devices.types.valve_base import ValveBase, db


class OnOffValve(ValveBase):
    __tablename__ = "onoff_valves"
