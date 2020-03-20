export async function getJSON(url) {
  const response = await fetch(url);
  return await response.json();
}

export async function postJSON(url, postdata) {
  const response = await fetch(url, {
    method: 'POST', headers: {
      'Content-Type': 'application/json'
    }, body: JSON.stringify(postdata)
  });
  try {
      return await response.json()
  } catch(error) {
      throw new Error(response.status);
  }
}
