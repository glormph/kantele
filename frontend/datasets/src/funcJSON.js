async function parseResponse(response) {
  let jsonresp;
  try {
    jsonresp = await response.json();
  } catch(error) {
    // Non-JSON responses, e.g. HTTP 500 server crash
    return {ok: false, error: 'Server error encountered', status: response.status};
  }
  // Deliver HTTP errors if any
  jsonresp.ok = response.ok;
  return jsonresp;
}


export async function getJSON(url) {
  let response;
  try {
    response = await fetch(url);
  } catch {
      return {ok: false, error: 'Kantele encountered a network error', status: false}
  }
  return parseResponse(response);
}


export async function postJSON(url, postdata) {
  let response;
  try {
    response = await fetch(url, {
      method: 'POST', headers: {
        'Content-Type': 'application/json'
      }, body: JSON.stringify(postdata)
    });
  } catch {
    return {ok: false, error: 'Kantele encountered a network error', status: false}
  }
  return parseResponse(response);
}
