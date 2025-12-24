
from typing import ClassVar

from modernrpc.jsonrpc.handler import JsonRpcHandler


class IAJSONRPCHandler(JsonRpcHandler):
    # Override content types because the IAPP sends an initialization request with the content type
    # text/plain, so we need to add that to the allowed content types for JSON-RPC. -- albertskja 2023-03-06
    valid_content_types: ClassVar[list[str]] = ["text/plain", "application/json", "application/json-rpc", "application/jsonrequest"]
