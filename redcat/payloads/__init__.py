import os

def get_payload_path(payload_name: str) -> str:
    return f"{os.path.dirname(os.path.realpath(__file__))}/{payload_name}"
