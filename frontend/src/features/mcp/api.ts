import {
  connectionsApiV1McpConnectionsGet,
  disconnectApiV1McpConnectionsGrantIdDelete,
  getConsentApiV1McpAuthorizationRequestIdGet,
  postConsentApiV1McpAuthorizationRequestIdPost,
} from "../../api/client";

export async function mcpRequest<T>(
  token: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const options = { auth: token, signal: init.signal };
  const method = init.method ?? "GET";
  const authorization = /^\/authorization\/([^/]+)$/.exec(path);
  const connection = /^\/connections\/([^/]+)$/.exec(path);
  const result =
    method === "GET" && path === "/connections"
      ? await connectionsApiV1McpConnectionsGet(options)
      : method === "DELETE" && connection
        ? await disconnectApiV1McpConnectionsGrantIdDelete({
            ...options,
            path: { grant_id: connection[1] },
          })
        : method === "GET" && authorization
          ? await getConsentApiV1McpAuthorizationRequestIdGet({
              ...options,
              path: { request_id: authorization[1] },
            })
          : method === "POST" && authorization
            ? await postConsentApiV1McpAuthorizationRequestIdPost({
                ...options,
                path: { request_id: authorization[1] },
                body: JSON.parse(String(init.body ?? "{}")),
              })
            : undefined;
  if (!result?.response?.ok) {
    throw new Error(
      result?.response?.status === 404
        ? "Request expired or unavailable. Start the connection again."
        : "Unable to complete the request. Please retry.",
    );
  }
  return result.data as T;
}
