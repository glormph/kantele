export async function getJSON(url) {
  let response;
  try {
    response = await fetch(url);
  } catch {
      return {error: 'Kantele encountered a network error', status: false}
  }
  if (!response.ok) {
      return {error: 'Kantele encountered a server error', status: response.status}
  }
  try {
    return await response.json();
  } catch(error) {
      return {error: 'Server error encountered', status: response.status};
  }
}

export async function postJSON(url, postdata) {
  const response = await fetch(url, {
    method: 'POST', headers: {
      'Content-Type': 'application/json'
    }, body: JSON.stringify(postdata)
  });
  if (!response.ok) {
      return {error: 'Kantele encountered a network error', status: false}
  }
  try {
      return await response.json()
  } catch(error) {
      return {error: 'Server error encountered', status: response.status};
  }
}
