from modernrpc.handlers import JSONRPCHandler


class IAJSONRPCHandler(JSONRPCHandler):

    # Override content types because the IAPP sends an initialization request with the content type
    # text/plain, so we need to add that to the allowed content types for JSON-RPC. -- albertskja 2023-03-06
    @staticmethod
    def valid_content_types():
        return [
            "text/plain",
            "application/json",
            "application/json-rpc",
            "application/jsonrequest",
        ]

    # Override process_single_request because the IAPP sends the jsonrpc version as a float, but the library expects it
    # as a string. So we need to overwrite that attribute to the correct type if it is a float. -- albertskja 2023-03-06
    def process_single_request(self, request_data, context):
        if request_data and isinstance(request_data, dict) and "jsonrpc" in request_data and isinstance(request_data['jsonrpc'], float):
            request_data['jsonrpc'] = str(request_data['jsonrpc'])
        return super().process_single_request(request_data=request_data, context=context)
