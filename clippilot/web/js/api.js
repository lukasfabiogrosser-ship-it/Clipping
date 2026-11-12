// Verbindung zum lokalen ClipPilot-Server.
async function call(method, path, data) {
  let res;
  try {
    res = await fetch(path, {
      method, headers: data !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
  } catch {
    throw new Error("ClipPilot antwortet nicht. Läuft das Start-Fenster noch?");
  }
  let json = null;
  try { json = await res.json(); } catch { /* leere Antwort */ }
  if (!res.ok) throw new Error(json?.error || `Fehler ${res.status}`);
  return json;
}
export const api = {
  get: p => call("GET", p), post: (p, d = {}) => call("POST", p, d), patch: (p, d) => call("PATCH", p, d),
  del: p => call("DELETE", p),
  // Upload mit Fortschritt (0..1)
  upload(file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", "/api/projects/upload?name=" + encodeURIComponent(file.name));
      xhr.upload.onprogress = e => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
      xhr.onload = () => {
        let json = null;
        try { json = JSON.parse(xhr.responseText); } catch { /* */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(json);
        else reject(new Error(json?.error || `Upload fehlgeschlagen (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error("Der Upload wurde unterbrochen."));
      xhr.send(file);
    });
  },
};
