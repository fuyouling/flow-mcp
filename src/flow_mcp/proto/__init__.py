"""Protobuf and gRPC stubs for flow-mcp."""
import sys
from pathlib import Path

_proto_dir = str(Path(__file__).parent.resolve())
if _proto_dir not in sys.path:
    sys.path.insert(0, _proto_dir)

from . import flow_pb2, flow_pb2_grpc

__all__ = ["flow_pb2", "flow_pb2_grpc"]
