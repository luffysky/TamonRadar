const DEFAULT_SITE = "https://tamonradar.snowrealm.pet";

async function getSite() {
  const { site } = await chrome.storage.sync.get("site");
  return site || DEFAULT_SITE;
}

(async () => {
  document.getElementById("site").value = await getSite();
})();

document.getElementById("go").addEventListener("click", async () => {
  const q = document.getElementById("q").value.trim();
  const site = await getSite();
  chrome.tabs.create({ url: q ? `${site}/?q=${encodeURIComponent(q)}` : site });
});

document.getElementById("save").addEventListener("click", async () => {
  const site = document.getElementById("site").value.trim().replace(/\/+$/, "");
  await chrome.storage.sync.set({ site });
  document.getElementById("save").textContent = "已儲存 ✓";
});
