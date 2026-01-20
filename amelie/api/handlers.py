import json
from http import HTTPStatus

from typing import ClassVar

from modernrpc import RpcRequestContext
from modernrpc.jsonrpc.handler import JsonRpcHandler


class IAJSONRPCHandler(JsonRpcHandler):
    # Override content types because the IAPP sends an initialization request with the content type
    # text/plain, so we need to add that to the allowed content types for JSON-RPC. -- albertskja 2023-03-06
    valid_content_types: ClassVar[list[str]] = ["text/plain", "application/json", "application/json-rpc", "application/jsonrequest"]

    # Override process_single_request because the IAPP sends the jsonrpc version as a float, but the library expects it
    # as a string. So we need to overwrite that attribute to the correct type if it is a float. -- albertskja 2023-03-06
    def process_request(self, request_body: str, context: RpcRequestContext) -> str | tuple[HTTPStatus, str]:
        request_data = json.loads(request_body)
        if request_data and isinstance(request_data, dict) and "jsonrpc" in request_data and isinstance(request_data['jsonrpc'], float):
            request_data['jsonrpc'] = str(request_data['jsonrpc'])
        new_request_body = json.dumps(request_data)
        return super().process_request(request_body=new_request_body, context=context)
